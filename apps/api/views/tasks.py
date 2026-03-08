"""
API задач (Work source_type='task' + TaskWork).

Аналог Flask-эндпоинтов:
  GET    /api/tasks           — список задач с фильтрацией и пагинацией
  POST   /api/tasks           — создание задачи
  PUT    /api/tasks/<id>      — обновление задачи (+ optimistic locking, _mcc_finish)
  DELETE /api/tasks/<id>      — удаление задачи
  DELETE /api/tasks/all       — удаление ВСЕХ задач (admin)
  GET    /api/tasks/<id>/executors — список исполнителей задачи
"""
# Стандартный модуль JSON
import json
# Стандартный логгер
import logging
# date — тип для работы с датами без времени
from datetime import date as dt_date

# transaction — атомарные операции с БД
from django.db import transaction
# Q — объект для сложных ORM-фильтров (OR/AND)
from django.db.models import Q, Count
# JsonResponse — HTTP-ответ в формате JSON
from django.http import JsonResponse
# method_decorator — применение декоратора к методу класса
from django.utils.decorators import method_decorator
# View — базовый класс для CBV
from django.views import View
# csrf_exempt — отключение CSRF-защиты для API
from django.views.decorators.csrf import csrf_exempt

# Миксины авторизации: login, writer, admin
from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    AdminRequiredJsonMixin,
    parse_json_body,
)
# Утилиты: фильтр видимости, нормализация plan_hours, валидаторы
from apps.api.utils import (
    get_visibility_filter,
    norm_plan_hours,
    parse_json_hours,
    mcc_finish_data,
    PRODUCTION_ALLOWED_FIELDS,
    validate_plan_hours,
    validate_executors_list,
    validate_actions,
)
# Модели: Work (базовая), TaskWork (детали задачи), TaskExecutor (исполнители),
# WorkReport (отчёты), PPWork (детали ПП), Project (УП-проект),
# WorkType (тип работы), AuditLog (аудит)
from apps.works.models import (
    Work, TaskWork, TaskExecutor, WorkReport, PPWork, Project, WorkType, AuditLog,
)
# Модели сотрудников
from apps.employees.models import Employee, Department, Sector, NTCCenter
# Функция записи в аудит-лог
from apps.api.audit import log_action

# Логгер для данного модуля
logger = logging.getLogger(__name__)

# Максимальное количество задач в одном ответе (ограничение пагинации)
TASKS_MAX = 500


# ---------------------------------------------------------------------------
#  Сериализация
# ---------------------------------------------------------------------------

def _serialize_task(work, task_detail=None, executors_data=None,
                    pp_labor_map=None):
    """
    Сериализует Work + TaskWork в плоский dict для JSON-ответа.
    Аналог Flask-формирования строки для /api/tasks GET.
    """
    d = {
        'id': work.id,                            # первичный ключ задачи
        # Тип задачи: имя WorkType или пустая строка
        'task_type': (work.work_type.name if work.work_type else '') or '',
        # Код отдела (из FK на Department)
        'dept': (work.department.code if work.department else '') or '',
        # Код сектора (из FK на Sector)
        'sector': (work.sector.code if work.sector else '') or '',
        # Название проекта (из FK на Project через property .name)
        'project': (work.project.name if work.project else '') or '',
        'work_name': work.work_name or '',         # наименование работы
        'work_number': work.work_number or '',     # номер/обозначение работы
        'description': work.description or '',     # описание задачи
        # Исполнитель: предпочитаем полное имя из FK Employee, fallback → raw-строка
        'executor': (work.executor.full_name if work.executor else
                     work.executor_name_raw) or '',
        # Даты в ISO-формате (пустая строка если None)
        'date_start': work.date_start.isoformat() if work.date_start else '',
        'date_end': work.date_end.isoformat() if work.date_end else '',
        'deadline': work.deadline.isoformat() if work.deadline else '',
        # plan_hours: словарь {YYYY-MM: float} (или {} если не заполнен)
        'plan_hours': work.plan_hours or {},
        # ID пользователя-создателя
        'created_by': work.created_by_id,
        # Временные метки в ISO-формате
        'created_at': work.created_at.isoformat() if work.created_at else '',
        'updated_at': work.updated_at.isoformat() if work.updated_at else '',
        # Код НТЦ-центра
        'center': (work.ntc_center.code if work.ntc_center else '') or '',
    }

    # TaskWork-специфичные поля (загружаем lazy или из prefetch-кэша)
    if task_detail is None:
        # Пробуем взять из атрибута prefetch-кэша (если вьюха его подготовила)
        task_detail = getattr(work, '_prefetched_task_detail', None)
        if task_detail is None:
            try:
                # Прямой доступ через OneToOne (дополнительный SELECT если нет prefetch)
                task_detail = work.task_detail
            except TaskWork.DoesNotExist:
                task_detail = None

    if task_detail:
        # Данные из TaskWork
        d['stage'] = task_detail.stage or ''             # номер этапа
        d['justification'] = task_detail.justification or ''  # обоснование
        d['actions'] = task_detail.actions or {}          # доп. данные (JSON)
    else:
        # TaskWork отсутствует — пустые значения
        d['stage'] = ''
        d['justification'] = ''
        d['actions'] = {}

    # Список исполнителей (передаётся извне для избежания N+1)
    execs = executors_data or []
    d['executors_list'] = execs

    # Агрегация plan_hours по всем исполнителям (суммируем по каждому месяцу)
    ph_all = {}
    for ex in execs:
        for k, v in (ex.get('hours') or {}).items():
            try:
                # Суммируем часы для одного месяца по всем исполнителям
                ph_all[k] = ph_all.get(k, 0) + (float(v) if v else 0)
            except (ValueError, TypeError):
                pass  # Игнорируем невалидные значения
    d['plan_hours_all'] = ph_all  # Итоговые часы (сумма по всем исполнителям)

    # pp_labor: трудозатраты из ПП (строка)
    pp_labor = ''
    if pp_labor_map and work.id in pp_labor_map:
        # Берём из предварительно загруженного словаря
        pp_labor = pp_labor_map[work.id]
    elif isinstance(d['actions'], dict):
        # Или из поля actions задачи (если было сохранено при синхронизации)
        pp_labor = d['actions'].get('pp_labor', '')
    d['pp_labor'] = pp_labor

    # from_pp: True если задача перенесена из производственного плана
    # Признак: в actions присутствует 'pp_id' — ссылка на строку ПП
    d['from_pp'] = bool(isinstance(d['actions'], dict) and d['actions'].get('pp_id'))

    return d


# ---------------------------------------------------------------------------
#  GET / POST  /api/tasks
# ---------------------------------------------------------------------------

# Отключаем CSRF для всего класса
@method_decorator(csrf_exempt, name='dispatch')
class TaskListView(LoginRequiredJsonMixin, View):
    """GET — список задач; POST — создание задачи."""

    def get(self, request):
        try:
            return self._get_tasks(request)
        except Exception as e:
            logger.error("TaskListView.get error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _get_tasks(self, request):
        # Параметры пагинации: limit — максимум записей в ответе
        try:
            limit = int(request.GET.get('limit', 0)) or TASKS_MAX
        except (ValueError, TypeError):
            limit = TASKS_MAX
        # Не превышаем глобальный максимум
        limit = min(limit, TASKS_MAX)

        # offset — смещение (для постраничной загрузки)
        try:
            offset = int(request.GET.get('offset', 0))
        except (ValueError, TypeError):
            offset = 0

        # Фильтр по году (строка '2024')
        year = request.GET.get('year')
        # Фильтр по месяцу (строка '3')
        month = request.GET.get('month')
        if request.GET.get('all') == '1':
            # Параметр all=1 — убираем фильтры по дате (показываем все записи)
            year = None
            month = None
        # Строка поиска (по нескольким полям)
        search = request.GET.get('search', '').strip().lower()

        # Базовый queryset: только задачи (не строки ПП)
        qs = Work.objects.filter(source_type=Work.SOURCE_TASK)

        # Применяем фильтр видимости по роли текущего пользователя
        vis_q = get_visibility_filter(request.user)
        qs = qs.filter(vis_q)

        # Фильтр по году и месяцу: задача считается «в периоде» если пересекается
        if year and month:
            try:
                yr = int(year)
                mn = int(month)
                from datetime import date
                # Начало и конец выбранного месяца
                sel_start = date(yr, mn, 1)
                if mn < 12:
                    sel_end = date(yr, mn + 1, 1)
                else:
                    sel_end = date(yr + 1, 1, 1)
                # Задача попадает в период если:
                # 1. Все даты пустые (задача без дат — показываем всегда)
                # 2. Есть date_start и date_end, и они пересекаются с периодом
                # 3. Есть date_start и deadline (вместо date_end)
                # 4. Есть только date_start (без даты конца)
                # 5. Есть только date_end или deadline
                qs = qs.filter(
                    Q(date_start__isnull=True, date_end__isnull=True, deadline__isnull=True)
                    | Q(date_start__lt=sel_end, date_end__gte=sel_start)
                    | Q(date_start__lt=sel_end, date_end__isnull=True,
                        deadline__gte=sel_start)
                    | Q(date_start__lt=sel_end, date_end__isnull=True,
                        deadline__isnull=True)
                    | Q(date_end__gte=sel_start, date_start__isnull=True)
                    | Q(date_end__isnull=True, deadline__gte=sel_start,
                        date_start__isnull=True)
                )
            except (ValueError, TypeError):
                pass  # Невалидные год/месяц — игнорируем фильтр
        elif year:
            # Фильтр только по году (без месяца)
            try:
                yr = int(year)
                from datetime import date
                yr_start = date(yr, 1, 1)
                yr_end = date(yr + 1, 1, 1)
                # Аналогичная логика пересечения с годом
                qs = qs.filter(
                    Q(date_start__isnull=True, date_end__isnull=True, deadline__isnull=True)
                    | Q(date_start__lt=yr_end, date_end__gte=yr_start)
                    | Q(date_start__lt=yr_end, date_end__isnull=True,
                        deadline__gte=yr_start)
                    | Q(date_start__lt=yr_end, date_end__isnull=True,
                        deadline__isnull=True)
                    | Q(date_end__gte=yr_start, date_start__isnull=True)
                    | Q(date_end__isnull=True, deadline__gte=yr_start,
                        date_start__isnull=True)
                )
            except (ValueError, TypeError):
                pass

        # Полнотекстовый поиск по нескольким полям (OR-логика)
        if search:
            s = search
            qs = qs.filter(
                Q(work_name__icontains=s)              # в названии задачи
                | Q(executor__last_name__icontains=s)  # в фамилии исполнителя (FK)
                | Q(executor_name_raw__icontains=s)    # в raw-строке исполнителя
                | Q(department__code__icontains=s)     # в коде отдела
                | Q(description__icontains=s)          # в описании
                | Q(project__name_short__icontains=s)  # в кратком названии проекта
                | Q(project__name_full__icontains=s)   # в полном названии проекта
                | Q(work_type__name__icontains=s)      # в типе задачи
                | Q(work_number__icontains=s)          # в номере/обозначении
            )

        # Подсчёт общего количества до применения LIMIT/OFFSET
        # (нужен для отображения пагинации на фронтенде)
        total_count = qs.count()

        # Оптимизация: select_related — JOIN для FK-полей (без N+1)
        # prefetch_related — отдельный запрос для обратных FK (task_detail, task_executors)
        qs = qs.select_related(
            'work_type', 'department', 'sector', 'project',
            'executor', 'ntc_center', 'created_by', 'task_detail',
        ).prefetch_related(
            'task_executors',
        ).order_by('-id')  # Новые задачи сначала
        # Применяем пагинацию через срез
        qs = qs[offset:offset + limit]

        # Материализуем queryset (выполняем SQL)
        works = list(qs)

        # Собираем TaskWork и TaskExecutor из prefetch-кэша (0 доп. запросов)
        task_details = {}   # work.id → TaskWork
        executors_data = {} # work.id → [{'name': ..., 'hours': ...}]
        for w in works:
            try:
                # Получаем TaskWork из prefetch-кэша
                td = w.task_detail
                task_details[w.id] = td
            except TaskWork.DoesNotExist:
                pass  # У задачи нет TaskWork (нештатная ситуация)
            # Собираем исполнителей из prefetch-кэша task_executors
            execs = []
            for te in w.task_executors.all():
                execs.append({
                    'name': te.executor_name,                   # имя исполнителя
                    'hours': parse_json_hours(te.plan_hours),   # план часов (dict)
                })
            if execs:
                executors_data[w.id] = execs

        # Загрузка pp_labor из связанных строк ПП (для задач, перенесённых из ПП)
        pp_labor_map = {}    # work.id → строка с трудозатратами
        pp_ids_needed = {}   # work.id → pp_work_id (нужно подгрузить из PPWork)
        for w in works:
            td = task_details.get(w.id)
            if td and isinstance(td.actions, dict):
                # Проверяем наличие pp_id в actions
                pp_id = td.actions.get('pp_id')
                # Проверяем, сохранено ли pp_labor непосредственно в actions
                pp_labor_val = td.actions.get('pp_labor')
                if pp_id:
                    if pp_labor_val:
                        # Уже есть в actions — используем его
                        pp_labor_map[w.id] = pp_labor_val
                    else:
                        # Нет в actions — нужно загрузить из PPWork
                        pp_ids_needed[w.id] = pp_id

        if pp_ids_needed:
            # Загружаем трудозатраты из PPWork одним запросом (batch)
            pp_id_list = list(set(pp_ids_needed.values()))
            pp_works = PPWork.objects.filter(work_id__in=pp_id_list).values(
                'work_id', 'labor',
            )
            # Строим словарь: pp_work_id → строковое значение labor
            pp_labor_by_id = {
                pw['work_id']: str(pw['labor']) for pw in pp_works
                if pw['labor'] is not None
            }
            # Заполняем pp_labor_map для задач
            for wid, ppid in pp_ids_needed.items():
                if ppid in pp_labor_by_id:
                    pp_labor_map[wid] = pp_labor_by_id[ppid]

        # Определяем ключ месяца для вычисления plan_hours_month
        month_key = None
        if year and month:
            try:
                # Формат 'YYYY-MM' для поиска в словаре plan_hours
                month_key = f"{int(year)}-{int(month):02d}"
            except (ValueError, TypeError):
                month_key = None

        # Формируем финальный результат
        result = []
        for w in works:
            td = task_details.get(w.id)
            execs = executors_data.get(w.id, [])
            # Сериализуем задачу в dict
            d = _serialize_task(w, task_detail=td, executors_data=execs,
                                pp_labor_map=pp_labor_map)
            # plan_hours_month: часы конкретного месяца (для отображения в таблице)
            if month_key:
                d['plan_hours_month'] = d['plan_hours_all'].get(month_key, '')
            else:
                d['plan_hours_month'] = ''
            result.append(d)

        # Формируем ответ
        response = JsonResponse(result, safe=False)
        # X-Total-Count: общее количество записей (без LIMIT) — для пагинации
        response['X-Total-Count'] = total_count
        return response


# Отключаем CSRF
@method_decorator(csrf_exempt, name='dispatch')
class TaskCreateView(WriterRequiredJsonMixin, View):
    """POST /api/tasks — создание задачи."""

    def post(self, request):
        try:
            return self._create(request)
        except Exception as e:
            logger.error("TaskCreateView error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _create(self, request):
        # Парсим JSON-тело запроса
        d = parse_json_body(request)
        if not d:
            # Пустое тело недопустимо при создании
            return JsonResponse({'error': 'Пустое тело запроса'}, status=400)

        # Профиль текущего пользователя (создатель задачи)
        employee = getattr(request.user, 'employee', None)

        # Серверная проверка прав по роли: dept_head/dept_deputy — только свой отдел
        if employee and employee.role in ('dept_head', 'dept_deputy'):
            dept_val = (d.get('dept') or '').strip()
            if dept_val and employee.department and dept_val != employee.department.code:
                return JsonResponse(
                    {'error': 'Вы можете создавать задачи только для своего отдела'}, status=403
                )

        # sector_head — только свой отдел и свой сектор
        if employee and employee.role == 'sector_head':
            dept_val = (d.get('dept') or '').strip()
            if dept_val and employee.department and dept_val != employee.department.code:
                return JsonResponse(
                    {'error': 'Вы можете создавать задачи только для своего отдела'}, status=403
                )
            sector_val = (d.get('sector') or '').strip()
            if sector_val and employee.sector:
                own_sector_values = {employee.sector.code, employee.sector.name}
                if sector_val not in own_sector_values:
                    return JsonResponse(
                        {'error': 'Вы можете создавать задачи только для своего сектора'}, status=403
                    )

        # Валидируем и нормализуем plan_hours
        ph, ph_err = validate_plan_hours(d.get('plan_hours'))
        if ph_err:
            return JsonResponse({'error': ph_err}, status=400)

        # Валидируем список исполнителей
        executors_list, el_err = validate_executors_list(d.get('executors_list'))
        if el_err:
            return JsonResponse({'error': el_err}, status=400)

        # Валидируем поле actions
        actions, act_err = validate_actions(d.get('actions'))
        if act_err:
            return JsonResponse({'error': act_err}, status=400)

        # Создаём Work и TaskWork в одной транзакции
        with transaction.atomic():
            # Создаём базовую запись Work
            work = Work(
                source_type=Work.SOURCE_TASK,               # тип: задача
                work_name=d.get('work_name', ''),           # наименование
                work_number=d.get('work_number', ''),       # номер/обозначение
                description=d.get('description', ''),       # описание
                executor_name_raw=d.get('executor', ''),    # исполнитель (raw)
                plan_hours=ph,                              # плановые часы
                created_by=employee,                        # создатель
            )

            # FK-поля через текстовое значение (как во Flask)
            # Устанавливает work.work_type, work.department, work.sector,
            # work.project, work.executor, work.ntc_center
            _set_work_fk_fields(work, d, request)

            # Устанавливает work.date_start, work.date_end, work.deadline
            _set_date_fields(work, d)

            # Сохраняем Work в БД
            work.save()

            # Создаём связанный TaskWork (детали задачи)
            TaskWork.objects.create(
                work=work,
                stage=d.get('stage', ''),               # номер этапа
                justification=d.get('justification', ''),  # обоснование
                actions=actions,                         # доп. данные
            )

            # Если есть исполнители — сохраняем их
            if executors_list:
                _save_executors(work, executors_list)

        # Записываем в аудит-лог факт создания задачи
        log_action(request, AuditLog.ACTION_TASK_CREATE,
                   object_id=work.id, object_repr=work.work_name)
        # Возвращаем ID созданной задачи
        return JsonResponse({'id': work.id})


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/tasks/<id>
# ---------------------------------------------------------------------------

# Отключаем CSRF
@method_decorator(csrf_exempt, name='dispatch')
class TaskDetailView(WriterRequiredJsonMixin, View):
    """PUT /api/tasks/<id>; DELETE /api/tasks/<id>."""

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except Exception as e:
            logger.error("TaskDetailView.put error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def delete(self, request, pk):
        try:
            # Ищем задачу по PK, убеждаемся что это именно задача (не строка ПП)
            work = Work.objects.filter(
                pk=pk, source_type=Work.SOURCE_TASK
            ).first()
            if not work:
                return JsonResponse({'error': 'Задача не найдена'}, status=404)
            # Записываем удаление в аудит до фактического удаления
            log_action(request, AuditLog.ACTION_TASK_DELETE,
                       object_id=work.id, object_repr=work.work_name)
            # Удаляем Work — CASCADE удалит TaskWork, TaskExecutor, WorkReport
            work.delete()  # CASCADE удалит TaskWork, TaskExecutor, WorkReport
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error("TaskDetailView.delete error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _update(self, request, pk):
        # Парсим JSON-тело
        d = parse_json_body(request)
        if not d:
            return JsonResponse({'error': 'Пустое тело запроса'}, status=400)

        # Загружаем задачу с prefetch TaskWork (select_related для OneToOne)
        work = Work.objects.filter(
            pk=pk, source_type=Work.SOURCE_TASK
        ).select_related('task_detail').first()
        if not work:
            return JsonResponse({'error': 'Задача не найдена'}, status=404)

        # ------ _mcc_finish: закрытие задачи в конце месяца ------
        if d.get('_mcc_finish'):
            # Специальная операция: обрезаем план часов и устанавливаем date_end
            return self._mcc_finish(work)

        # ------ Optimistic locking ------
        # Клиент передаёт updated_at из предыдущей загрузки
        if 'updated_at' in d and d['updated_at'] is not None:
            # Сравниваем с актуальным значением в БД
            db_updated = str(work.updated_at)
            if db_updated != str(d['updated_at']):
                # Запись изменилась — сообщаем о конфликте (HTTP 409)
                return JsonResponse({
                    'error': 'conflict',
                    'message': 'Запись была изменена другим пользователем. '
                               'Перезагрузите страницу.',
                }, status=409)

        # from_pp: разрешаем изменять только даты, план.часы и исполнителей
        task_detail = None
        try:
            task_detail = work.task_detail
        except TaskWork.DoesNotExist:
            pass  # TaskWork отсутствует (нештатная ситуация)
        # Определяем, является ли задача перенесённой из ПП
        is_from_pp = bool(
            task_detail and isinstance(task_detail.actions, dict)
            and task_detail.actions.get('pp_id')  # наличие pp_id = признак переноса
        )
        # Для задач, перенесённых из ПП, блокируем изменение ключевых полей
        if is_from_pp and not d.get('_mcc_finish'):
            # Удаляем из входных данных поля, которые нельзя менять
            for lf in ('work_name', 'work_number', 'description',
                       'task_type', 'dept', 'sector', 'project',
                       'stage', 'justification'):
                d.pop(lf, None)

        with transaction.atomic():
            # Обновление plan_hours (частичное или полное)
            if 'plan_hours_update' in d:
                # Частичное обновление: обновляем только переданные месяцы
                ph_upd, ph_err = validate_plan_hours(d['plan_hours_update'])
                if ph_err:
                    return JsonResponse({'error': ph_err}, status=400)
                # Мержим с существующими значениями
                existing = parse_json_hours(work.plan_hours)
                existing.update(ph_upd)
                work.plan_hours = existing
                # Сохраняем только поля plan_hours и updated_at
                work.save(update_fields=['plan_hours', 'updated_at'])
            else:
                # Полное обновление Work
                if 'plan_hours' in d:
                    # Новый plan_hours передан явно — валидируем и заменяем
                    ph, ph_err = validate_plan_hours(d.get('plan_hours'))
                    if ph_err:
                        return JsonResponse({'error': ph_err}, status=400)
                else:
                    # plan_hours не передан — сохраняем существующий
                    ph = work.plan_hours
                if not is_from_pp:
                    # Обновляем текстовые поля только для не-PP задач
                    work.work_name = d.get('work_name', work.work_name)
                    work.work_number = d.get('work_number', work.work_number)
                    work.description = d.get('description', work.description)
                # Исполнитель обновляется всегда (даже для from_pp задач)
                work.executor_name_raw = d.get('executor', work.executor_name_raw)
                work.plan_hours = ph

                # Обновляем FK-поля
                _set_work_fk_fields(work, d, request)
                # Обновляем поля дат
                _set_date_fields(work, d)
                # Полное сохранение Work
                work.save()

            # Обновление TaskWork (детали задачи)
            try:
                td = work.task_detail
            except TaskWork.DoesNotExist:
                # TaskWork не существует — создаём новый (без сохранения пока)
                td = TaskWork(work=work)

            if 'stage' in d and not is_from_pp:
                # Обновляем этап только для не-PP задач
                td.stage = d['stage']
            if 'justification' in d and not is_from_pp:
                # Обоснование — только для не-PP задач
                td.justification = d['justification']
            if 'actions' in d:
                # actions можно обновлять всегда (например, добавить pp_labor)
                actions, act_err = validate_actions(d['actions'])
                if act_err:
                    return JsonResponse({'error': act_err}, status=400)
                td.actions = actions
            # Сохраняем TaskWork
            td.save()

            # Обновление списка исполнителей
            if 'executors_list' in d:
                executors_list, el_err = validate_executors_list(d['executors_list'])
                if el_err:
                    return JsonResponse({'error': el_err}, status=400)
                # Удаляем старых исполнителей и создаём новых
                TaskExecutor.objects.filter(work=work).delete()
                if executors_list:
                    _save_executors(work, executors_list)

        # Записываем в аудит-лог обновление задачи
        log_action(request, AuditLog.ACTION_TASK_UPDATE,
                   object_id=work.id, object_repr=work.work_name)
        return JsonResponse({'ok': True})

    def _mcc_finish(self, work):
        """Закрытие задачи: date_end = последний день прошлого месяца,
        plan_hours обрезаются до прошлого месяца."""
        # Получаем последний день предыдущего месяца и ключ-граница
        last_day, cutoff = mcc_finish_data()
        # Парсим текущий plan_hours
        ph = parse_json_hours(work.plan_hours)
        # Оставляем только записи, которые раньше текущего месяца
        ph = {k: v for k, v in ph.items() if k < cutoff}

        # Устанавливаем дату окончания = последний день прошлого месяца
        work.date_end = last_day
        work.plan_hours = ph
        # Сохраняем только изменённые поля (+ updated_at автоматически)
        work.save(update_fields=['date_end', 'plan_hours', 'updated_at'])
        return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
#  DELETE /api/tasks/all (admin)
# ---------------------------------------------------------------------------

# Отключаем CSRF
@method_decorator(csrf_exempt, name='dispatch')
class TaskDeleteAllView(AdminRequiredJsonMixin, View):
    """DELETE /api/tasks/all — удаление всех задач (только admin)."""

    def delete(self, request):
        try:
            with transaction.atomic():
                # Удаляем все Work с source_type='task'
                # CASCADE удалит TaskWork, TaskExecutor и связанные записи
                Work.objects.filter(source_type=Work.SOURCE_TASK).delete()
            # Логируем факт очистки всех задач администратором
            logger.info("Администратор очистил все задачи: user=%s",
                        request.user.pk)
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error("TaskDeleteAllView error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  GET /api/tasks/<id>/executors
# ---------------------------------------------------------------------------

# Отключаем CSRF
@method_decorator(csrf_exempt, name='dispatch')
class TaskExecutorsView(LoginRequiredJsonMixin, View):
    """GET /api/tasks/<id>/executors — список исполнителей задачи."""

    def get(self, request, pk):
        try:
            # Получаем всех исполнителей данной задачи
            executors = TaskExecutor.objects.filter(work_id=pk)
            # Сериализуем в список dict
            result = [
                {
                    'name': te.executor_name,                  # имя исполнителя
                    'hours': parse_json_hours(te.plan_hours),  # план часов
                }
                for te in executors
            ]
            return JsonResponse(result, safe=False)
        except Exception as e:
            logger.error("TaskExecutorsView error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  Вспомогательные функции
# ---------------------------------------------------------------------------

def _set_work_fk_fields(work, d, request):
    """Устанавливает FK-поля Work по текстовым значениям из запроса."""
    # work_type / task_type — тип задачи (get_or_create по названию)
    task_type = d.get('task_type', '')
    if task_type:
        # Ищем или создаём WorkType по имени
        wt, _ = WorkType.objects.get_or_create(name=task_type)
        work.work_type = wt

    # department / dept — отдел по коду
    dept = d.get('dept', '')
    if dept:
        dep_obj = Department.objects.filter(code=dept).first()
        if dep_obj:
            work.department = dep_obj

    # sector — сектор по коду (в рамках отдела)
    sector = d.get('sector', '')
    if sector and work.department:
        # Ищем сектор только в рамках уже установленного отдела
        sec_obj = Sector.objects.filter(
            code=sector, department=work.department,
        ).first()
        if sec_obj:
            work.sector = sec_obj

    # project — УП-проект по названию
    project = d.get('project', '')
    if project:
        # name — @property (name_short or name_full), в БД поля нет.
        # Ищем сначала по name_short, затем по name_full.
        proj_obj = (
            Project.objects.filter(name_short=project).first()
            or Project.objects.filter(name_full=project).first()
        )
        if proj_obj:
            work.project = proj_obj

    # executor — пытаемся найти Employee по ФИО
    executor = d.get('executor', '')
    if executor:
        # Сохраняем raw-строку в любом случае
        work.executor_name_raw = executor
        # Пробуем найти Employee по фамилии (первое слово)
        parts = executor.split()
        emp = Employee.objects.filter(
            last_name__icontains=parts[0]
        ).first() if parts else None
        if emp and emp.full_name == executor:
            # Точное совпадение полного имени — привязываем FK
            work.executor = emp
        else:
            # Имя не совпало точно — сбрасываем FK (raw-строка всё равно сохранена)
            work.executor = None

    # center (НТЦ) — берём из профиля пользователя (не из запроса);
    # фолбэк на НТЦ отдела (актуально для dept_head / dept_deputy)
    employee = getattr(request.user, 'employee', None)
    effective_ntc = employee.effective_ntc_center if employee else None
    if effective_ntc:
        work.ntc_center = effective_ntc


def _set_date_fields(work, d):
    """Устанавливает поля дат из строковых значений."""
    # Перебираем три поля дат: начало, конец, дедлайн
    for field_name, attr in [
        ('date_start', 'date_start'),
        ('date_end', 'date_end'),
        ('deadline', 'deadline'),
    ]:
        val = d.get(field_name)
        if val is not None:
            if val == '':
                # Пустая строка → очищаем поле (NULL в БД)
                setattr(work, attr, None)
            else:
                try:
                    # Парсим ISO-строку ('YYYY-MM-DD') → объект date
                    setattr(work, attr, dt_date.fromisoformat(str(val)))
                except (ValueError, TypeError):
                    # Невалидная дата → None (не сохраняем мусор)
                    setattr(work, attr, None)


def _save_executors(work, executors):
    """Сохраняет список исполнителей задачи."""
    objs = []
    for ex in executors:
        # plan_hours исполнителя (может быть строкой JSON или dict)
        hours = ex.get('hours', {})
        if isinstance(hours, str):
            # Парсим строку JSON в dict
            hours = parse_json_hours(hours)
        objs.append(
            TaskExecutor(
                work=work,                                       # привязка к задаче
                executor_name=ex.get('name', ''),              # имя исполнителя
                plan_hours=hours if isinstance(hours, dict) else {},  # план часов
            )
        )
    if objs:
        # Создаём всех исполнителей одним SQL INSERT (оптимизация)
        TaskExecutor.objects.bulk_create(objs)
