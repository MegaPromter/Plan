"""
API задач (Work show_in_plan=True).

Аналог Flask-эндпоинтов:
  GET    /api/tasks           — список задач с фильтрацией и пагинацией
  POST   /api/tasks           — создание задачи
  PUT    /api/tasks/<id>      — обновление задачи (+ optimistic locking, _mcc_finish)
  DELETE /api/tasks/<id>      — удаление задачи
  DELETE /api/tasks/all       — удаление ВСЕХ задач (admin)
  GET    /api/tasks/<id>/executors — список исполнителей задачи
"""
import json
import logging
from datetime import date as dt_date

from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Exists, OuterRef, Q
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    AdminRequiredJsonMixin,
    parse_json_body,
)
from apps.api.utils import (
    get_visibility_filter,
    norm_plan_hours,
    parse_json_hours,
    mcc_finish_data,
    validate_plan_hours,
    validate_executors_list,
    validate_actions,
    validate_task_type,
    generate_row_code,
)
from apps.works.models import (
    Work, TaskExecutor, WorkReport, Project, AuditLog,
)
from apps.employees.models import Employee, Department, Sector, NTCCenter
from apps.api.audit import log_action
from apps.api.views.reports import _sync_notices_for_work

logger = logging.getLogger(__name__)

TASKS_MAX = 100000


# ---------------------------------------------------------------------------
#  Сериализация
# ---------------------------------------------------------------------------

def _build_pp_justification(work):
    """Формирует обоснование для ПП-записи: «ПП-план; Этап X; Веха Y; Работа Z»."""
    pp_plan_name = (work.pp_project.name or '') if work.pp_project else ''
    parts = [pp_plan_name] if pp_plan_name else []
    if work.stage_num:
        parts.append(f'Этап {work.stage_num}')
    if work.milestone_num:
        parts.append(f'Веха {work.milestone_num}')
    if work.work_num:
        parts.append(f'№ работы {work.work_num}')
    return '; '.join(parts)


def _serialize_task(work, executors_data=None, sector_heads=None):
    """
    Сериализует Work (show_in_plan=True) в плоский dict для JSON-ответа.
    Поля stage_num, work_num, work_designation — единые для ПП и СП.
    Для ПП-записей проект берётся из pp_project.up_project,
    обоснование формируется из ПП-полей, deadline = date_end.
    sector_heads — словарь {sector_code: short_name} для ФИО начальников секторов.
    """
    is_from_pp = work.show_in_pp

    # Проект: для ПП → pp_project.up_project, для чистых СП → project
    if is_from_pp:
        up_project = work.pp_project.up_project if work.pp_project else None
        project_name = (up_project.name if up_project else '') or ''
    else:
        project_name = (work.project.name if work.project else '') or ''

    # Трудоёмкость ПП (для справки)
    pp_labor_val = ''
    if is_from_pp and work.labor is not None:
        pp_labor_val = str(float(work.labor))

    # Сектор: всегда через FK
    sector_val = (work.sector.code if work.sector else '') or ''

    d = {
        'id': work.id,
        'row_code': work.row_code or '',     # код строки (автогенерация)
        'task_type': (work.task_type or 'Выпуск нового документа') if is_from_pp
                     else (work.task_type or ''),
        'dept': (work.department.code if work.department else '') or '',
        'sector': sector_val,
        'project': project_name,
        'work_name': work.work_name or '',
        # Единые поля (и ПП, и СП пишут/читают одни и те же колонки)
        'work_number': work.work_num or '',
        'description': work.work_designation or '',
        'executor': (work.executor.full_name if work.executor else '') or '',
        'date_start': work.date_start.isoformat() if work.date_start else '',
        'date_end': work.date_end.isoformat() if work.date_end else '',
        # Для ПП-записей deadline = date_end (срок из ПП)
        'deadline': (work.date_end.isoformat() if work.date_end else '') if is_from_pp
                    else (work.deadline.isoformat() if work.deadline else ''),
        'plan_hours': work.plan_hours or {},
        'created_by': work.created_by_id,
        'created_at': work.created_at.isoformat() if work.created_at else '',
        'updated_at': work.updated_at.isoformat() if work.updated_at else '',
        'center': (work.ntc_center.code if work.ntc_center else '') or '',
        # Единое поле этапа; обоснование для ПП формируется на лету
        'stage': work.stage_num or '',
        'justification': _build_pp_justification(work) if is_from_pp
                         else (work.justification or ''),
        'actions': work.actions or {},
        'sector_head': (sector_heads or {}).get(work.sector.code, '') if work.sector else '',
        'norm': float(work.norm) if work.norm is not None else None,
    }

    # Список исполнителей
    execs = executors_data or []
    d['executors_list'] = execs

    # Агрегация plan_hours по всем исполнителям
    ph_all = {}
    for ex in execs:
        for k, v in (ex.get('hours') or {}).items():
            try:
                ph_all[k] = ph_all.get(k, 0) + (float(v) if v else 0)
            except (ValueError, TypeError):
                pass
    d['plan_hours_all'] = ph_all

    d['pp_labor'] = pp_labor_val
    d['from_pp'] = is_from_pp
    d['predecessors_count'] = getattr(work, '_pred_count', 0) or 0
    d['has_reports'] = bool(getattr(work, '_has_reports', False))

    # Индикатор просроченности: deadline (или date_end) < сегодня
    today = timezone.now().date()
    effective_deadline = (work.date_end if is_from_pp else work.deadline) or work.date_end
    d['is_overdue'] = bool(
        effective_deadline and effective_deadline < today
    )

    return d


# ---------------------------------------------------------------------------
#  GET / POST  /api/tasks
# ---------------------------------------------------------------------------

class TaskListView(LoginRequiredJsonMixin, View):
    """GET — список задач."""

    def get(self, request):
        try:
            return self._get_tasks(request)
        except (ValueError, TypeError) as e:
            logger.warning("TaskListView.get bad request: %s", e)
            return JsonResponse({'error': f'Некорректные параметры: {e}'}, status=400)
        except Exception as e:
            logger.error("TaskListView.get error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _get_tasks(self, request):
        try:
            limit = int(request.GET.get('limit', 0)) or TASKS_MAX
        except (ValueError, TypeError):
            limit = TASKS_MAX
        limit = min(limit, TASKS_MAX)

        try:
            offset = int(request.GET.get('offset', 0))
        except (ValueError, TypeError):
            offset = 0

        year = request.GET.get('year')
        month = request.GET.get('month')
        if request.GET.get('all') == '1':
            year = None
            month = None
        search = request.GET.get('search', '').strip().lower()

        # Только задачи (не строки ПП)
        # СП — общий документ, видимый всем (аналогично ПП)
        qs = Work.objects.filter(show_in_plan=True)

        # Фильтр по периоду
        if year and month:
            try:
                yr = int(year)
                mn = int(month)
                if not (1 <= mn <= 12) or not (1900 <= yr <= 2100):
                    raise ValueError(f'Недопустимый период: {yr}-{mn}')
                from datetime import date
                sel_start = date(yr, mn, 1)
                sel_end = date(yr, mn + 1, 1) if mn < 12 else date(yr + 1, 1, 1)
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
                pass
        elif year:
            try:
                yr = int(year)
                if not (1900 <= yr <= 2100):
                    raise ValueError(f'Недопустимый год: {yr}')
                from datetime import date
                yr_start = date(yr, 1, 1)
                yr_end = date(yr + 1, 1, 1)
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

        # Полнотекстовый поиск
        if search:
            s = search
            qs = qs.filter(
                Q(work_name__icontains=s)
                | Q(executor__last_name__icontains=s)
                | Q(executor__first_name__icontains=s)
                | Q(department__code__icontains=s)
                | Q(work_designation__icontains=s)
                | Q(project__name_short__icontains=s)
                | Q(project__name_full__icontains=s)
                | Q(task_type__icontains=s)
                | Q(work_num__icontains=s)
            )

        total_count = qs.count()

        qs = qs.annotate(
            _pred_count=Count('predecessor_links'),
            _has_reports=Exists(WorkReport.objects.filter(work_id=OuterRef('pk'))),
        ).select_related(
            'department', 'sector', 'project',
            'executor', 'ntc_center', 'created_by',
            'pp_project', 'pp_project__up_project',
        ).prefetch_related(
            'task_executors', 'task_executors__executor',
        ).order_by('-id')
        qs = qs[offset:offset + limit]

        works = list(qs)

        # Собираем исполнителей из prefetch-кэша
        executors_data = {}
        for w in works:
            execs = []
            for te in w.task_executors.all():
                execs.append({
                    'name': te.executor.full_name if te.executor else te.executor_name,
                    'hours': parse_json_hours(te.plan_hours),
                })
            if execs:
                executors_data[w.id] = execs

        # Ключ месяца для plan_hours_month
        month_key = None
        if year and month:
            try:
                month_key = f"{int(year)}-{int(month):02d}"
            except (ValueError, TypeError):
                month_key = None

        # Словарь ФИО начальников секторов: {sector_code: "Фамилия И.О."}
        sector_heads = {}
        for emp in Employee.objects.filter(role=Employee.ROLE_SECTOR_HEAD).select_related('sector'):
            if emp.sector:
                parts = (emp.full_name or '').split()
                if len(parts) >= 3:
                    short = f'{parts[0]} {parts[1][0]}.{parts[2][0]}.'
                elif len(parts) == 2:
                    short = f'{parts[0]} {parts[1][0]}.'
                else:
                    short = emp.full_name or ''
                sector_heads[emp.sector.code] = short

        result = []
        for w in works:
            execs = executors_data.get(w.id, [])
            d = _serialize_task(w, executors_data=execs, sector_heads=sector_heads)
            d['plan_hours_month'] = d['plan_hours_all'].get(month_key, '') if month_key else ''
            result.append(d)

        response = JsonResponse(result, safe=False)
        response['X-Total-Count'] = total_count
        return response


class TaskCreateView(WriterRequiredJsonMixin, View):
    """POST /api/tasks — создание задачи."""

    def post(self, request):
        try:
            return self._create(request)
        except (ValueError, TypeError) as e:
            logger.warning("TaskCreateView bad request: %s", e)
            return JsonResponse({'error': f'Некорректные данные: {e}'}, status=400)
        except Exception as e:
            logger.error("TaskCreateView error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _create(self, request):
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        if not d:
            return JsonResponse({'error': 'Пустое тело запроса'}, status=400)

        employee = getattr(request.user, 'employee', None)

        # Проверка прав по роли
        if employee and employee.role in ('dept_head', 'dept_deputy'):
            dept_val = (d.get('dept') or '').strip()
            if dept_val and employee.department and dept_val != employee.department.code:
                return JsonResponse(
                    {'error': 'Вы можете создавать задачи только для своего отдела'}, status=403
                )

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

        ph, ph_err = validate_plan_hours(d.get('plan_hours'))
        if ph_err:
            return JsonResponse({'error': ph_err}, status=400)

        executors_list, el_err = validate_executors_list(d.get('executors_list'))
        if el_err:
            return JsonResponse({'error': el_err}, status=400)

        actions, act_err = validate_actions(d.get('actions'))
        if act_err:
            return JsonResponse({'error': act_err}, status=400)

        with transaction.atomic():
            work = Work(
                show_in_plan=True,
                work_name=d.get('work_name', ''),
                work_num=d.get('work_number', ''),
                work_designation=d.get('description', ''),
                plan_hours=ph,
                stage_num=d.get('stage', ''),
                justification=d.get('justification', ''),
                actions=actions,
                created_by=employee,
            )

            if 'task_type' in d:
                tt_val, tt_err = validate_task_type(d['task_type'])
                if tt_err:
                    return JsonResponse({'error': tt_err}, status=400)
                d['task_type'] = tt_val

            _set_work_fk_fields(work, d, request)
            _set_date_fields(work, d)
            work.save()

            # Автогенерация row_code
            if work.project and not work.row_code:
                work.row_code = generate_row_code(work.project)
                work.save(update_fields=['row_code'])

            if executors_list:
                _save_executors(work, executors_list)

        log_action(request, AuditLog.ACTION_TASK_CREATE,
                   object_id=work.id, object_repr=work.work_name)
        return JsonResponse({'id': work.id})


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/tasks/<id>
# ---------------------------------------------------------------------------

class TaskDetailView(WriterRequiredJsonMixin, View):
    """PUT /api/tasks/<id>; DELETE /api/tasks/<id>."""

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except (ValueError, TypeError) as e:
            logger.warning("TaskDetailView.put bad request: %s", e)
            return JsonResponse({'error': f'Некорректные данные: {e}'}, status=400)
        except Exception as e:
            logger.error("TaskDetailView.put error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def delete(self, request, pk):
        try:
            vis_q = get_visibility_filter(request.user)
            with transaction.atomic():
                # select_for_update: блокируем строку от конкурентных изменений
                work = (
                    Work.objects
                    .select_for_update()
                    .filter(pk=pk, show_in_plan=True)
                    .filter(vis_q)
                    .first()
                )
                if not work:
                    return JsonResponse({'error': 'Задача не найдена'}, status=404)
                log_action(request, AuditLog.ACTION_TASK_DELETE,
                           object_id=work.id, object_repr=work.work_name)
                if work.show_in_pp:
                    # Запись видна и в ПП — только убираем из СП, не удаляя
                    work.show_in_plan = False
                    work.actions = {}
                    work.save(update_fields=['show_in_plan', 'actions'])
                else:
                    work.delete()
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error("TaskDetailView.delete error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _update(self, request, pk):
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        if not d:
            return JsonResponse({'error': 'Пустое тело запроса'}, status=400)

        vis_q = get_visibility_filter(request.user)
        work = Work.objects.filter(pk=pk, show_in_plan=True).filter(vis_q).first()
        if not work:
            return JsonResponse({'error': 'Задача не найдена'}, status=404)

        if d.get('_mcc_finish'):
            return self._mcc_finish(work)

        # Optimistic locking: нормализуем оба timestamp до YYYY-MM-DDTHH:MM:SS
        # (отбрасываем микросекунды и TZ-суффикс для надёжного сравнения)
        if 'updated_at' in d and d['updated_at'] is not None:
            server_ts = (work.updated_at.strftime('%Y-%m-%dT%H:%M:%S')
                         if work.updated_at else '')
            raw = str(d['updated_at']).replace(' ', 'T')
            # Обрезаем микросекунды (.123456) и TZ-суффикс (+00:00 / Z)
            client_ts = raw[:19] if len(raw) >= 19 else raw
            if server_ts != client_ts:
                return JsonResponse({
                    'error': 'conflict',
                    'message': 'Запись была изменена другим пользователем. '
                               'Перезагрузите страницу.',
                }, status=409)

        # from_pp: запись из ПП — ПП-поля заблокированы для редактирования в СП
        is_from_pp = work.show_in_pp
        _PP_LOCKED_FIELDS = frozenset((
            'work_name', 'work_number', 'description',
            'task_type', 'dept', 'sector', 'project',
            'stage', 'justification', 'deadline',
        ))
        if is_from_pp and not d.get('_mcc_finish'):
            # Определяем какие заблокированные поля клиент пытался изменить
            attempted_locked = [lf for lf in _PP_LOCKED_FIELDS if lf in d]
            if attempted_locked:
                # Проверяем, остаются ли разрешённые поля
                non_service = {k for k in d if not k.startswith('_') and k != 'updated_at'}
                remaining = non_service - _PP_LOCKED_FIELDS
                if not remaining:
                    # Все переданные поля заблокированы — отклоняем
                    return JsonResponse({
                        'error': 'Запись из ПП: редактирование заблокированных полей запрещено',
                        'locked_fields': attempted_locked,
                    }, status=403)
                # Есть и разрешённые поля — тихо убираем заблокированные, добавим warning
                for lf in attempted_locked:
                    d.pop(lf, None)
                logger.info(
                    "PP lock: task %d — ignored locked fields %s",
                    pk, attempted_locked,
                )

        with transaction.atomic():
            if 'plan_hours_update' in d:
                ph_upd, ph_err = validate_plan_hours(d['plan_hours_update'])
                if ph_err:
                    return JsonResponse({'error': ph_err}, status=400)
                existing = parse_json_hours(work.plan_hours)
                existing.update(ph_upd)
                work.plan_hours = existing
                work.save(update_fields=['plan_hours', 'updated_at'])
            else:
                if 'plan_hours' in d:
                    ph, ph_err = validate_plan_hours(d.get('plan_hours'))
                    if ph_err:
                        return JsonResponse({'error': ph_err}, status=400)
                else:
                    ph = work.plan_hours
                if not is_from_pp:
                    work.work_name = d.get('work_name', work.work_name) or ''
                    work.work_num = d.get('work_number', work.work_num) or ''
                    work.work_designation = d.get('description', work.work_designation) or ''
                work.plan_hours = ph

                if 'task_type' in d:
                    tt_val, tt_err = validate_task_type(d['task_type'])
                    if tt_err:
                        return JsonResponse({'error': tt_err}, status=400)
                    d['task_type'] = tt_val

                _set_work_fk_fields(work, d, request)
                _set_date_fields(work, d)

                if 'stage' in d and not is_from_pp:
                    work.stage_num = d['stage']
                if 'justification' in d and not is_from_pp:
                    work.justification = d['justification']
                if 'actions' in d:
                    actions, act_err = validate_actions(d['actions'])
                    if act_err:
                        return JsonResponse({'error': act_err}, status=400)
                    work.actions = actions

                work.save()

                # Автогенерация row_code при назначении/смене проекта
                if 'project' in d and work.project:
                    work.row_code = generate_row_code(work.project)
                    work.save(update_fields=['row_code'])

                # Синхронизация ЖИ при смене task_type
                if 'task_type' in d:
                    _sync_notices_for_work(work)

            # Обновление списка исполнителей
            if 'executors_list' in d:
                executors_list, el_err = validate_executors_list(d['executors_list'])
                if el_err:
                    return JsonResponse({'error': el_err}, status=400)
                TaskExecutor.objects.filter(work=work).delete()
                if executors_list:
                    _save_executors(work, executors_list)

        log_action(request, AuditLog.ACTION_TASK_UPDATE,
                   object_id=work.id, object_repr=work.work_name)
        return JsonResponse({'ok': True})

    def _mcc_finish(self, work):
        """Закрытие задачи: date_end = последний день прошлого месяца."""
        last_day, cutoff = mcc_finish_data()
        ph = parse_json_hours(work.plan_hours)
        ph = {k: v for k, v in ph.items() if k < cutoff}
        work.date_end = last_day
        work.plan_hours = ph
        work.save(update_fields=['date_end', 'plan_hours', 'updated_at'])
        return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
#  DELETE /api/tasks/all (admin)
# ---------------------------------------------------------------------------

class TaskDeleteAllView(AdminRequiredJsonMixin, View):
    """DELETE /api/tasks/all — удаление всех задач (только admin)."""

    def delete(self, request):
        try:
            with transaction.atomic():
                # Записи, видимые и в ПП — только снимаем флаг СП
                Work.objects.filter(
                    show_in_plan=True, show_in_pp=True,
                ).update(show_in_plan=False, actions={})
                # Чистые СП-записи — удаляем
                Work.objects.filter(
                    show_in_plan=True, show_in_pp=False,
                ).delete()
            logger.info("Администратор очистил все задачи: user=%s", request.user.pk)
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error("TaskDeleteAllView error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  GET /api/tasks/<id>/executors
# ---------------------------------------------------------------------------

class TaskExecutorsView(LoginRequiredJsonMixin, View):
    """GET /api/tasks/<id>/executors — список исполнителей задачи."""

    def get(self, request, pk):
        try:
            vis_q = get_visibility_filter(request.user)
            if not Work.objects.filter(pk=pk, show_in_plan=True).filter(vis_q).exists():
                return JsonResponse({'error': 'Задача не найдена'}, status=403)
            executors = TaskExecutor.objects.filter(work_id=pk).select_related('executor')
            result = [
                {
                    'name': te.executor.full_name if te.executor else te.executor_name,
                    'hours': parse_json_hours(te.plan_hours),
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
    # task_type — теперь просто CharField (не FK на WorkType)
    task_type = d.get('task_type', '')
    if task_type:
        work.task_type = task_type

    # department / dept
    dept = d.get('dept', '')
    if dept:
        dep_obj = Department.objects.filter(code=dept).first()
        if dep_obj:
            work.department = dep_obj

    # sector
    sector = d.get('sector', '')
    if sector:
        if work.department:
            sec_obj = Sector.objects.filter(
                code=sector, department=work.department,
            ).first()
            if sec_obj:
                work.sector = sec_obj
            else:
                logger.warning(
                    "Сектор '%s' не найден для отдела '%s'",
                    sector, work.department.code,
                )
        else:
            # Попытка без привязки к отделу — ищем по коду
            sec_obj = Sector.objects.filter(code=sector).first()
            if sec_obj:
                work.sector = sec_obj
            else:
                logger.warning("Сектор '%s' не найден (отдел не задан)", sector)

    # project — УП-проект по названию
    project = d.get('project', '')
    if project:
        proj_obj = (
            Project.objects.filter(name_short=project).first()
            or Project.objects.filter(name_full=project).first()
        )
        if proj_obj:
            work.project = proj_obj

    # executor — поиск по ФИО (фамилия + имя + отчество)
    executor = d.get('executor', '')
    if executor:
        parts = executor.split()
        qs = Employee.objects.all()
        if parts:
            qs = qs.filter(last_name__iexact=parts[0])
        if len(parts) >= 2:
            qs = qs.filter(first_name__iexact=parts[1])
        if len(parts) >= 3:
            qs = qs.filter(patronymic__iexact=parts[2])
        emp = qs.first() if parts else None
        work.executor = emp if (emp and emp.full_name == executor) else None

    # center — из профиля пользователя (только при создании, чтобы не
    # перезаписывать НТЦ при обновлении чужим пользователем)
    if not work.pk:
        employee = getattr(request.user, 'employee', None)
        effective_ntc = employee.effective_ntc_center if employee else None
        if effective_ntc:
            work.ntc_center = effective_ntc


def _set_date_fields(work, d):
    """Устанавливает поля дат из строковых значений."""
    for field_name, attr in [
        ('date_start', 'date_start'),
        ('date_end', 'date_end'),
        ('deadline', 'deadline'),
    ]:
        val = d.get(field_name)
        if val is not None:
            if val == '':
                setattr(work, attr, None)
            else:
                try:
                    setattr(work, attr, dt_date.fromisoformat(str(val)))
                except (ValueError, TypeError):
                    setattr(work, attr, None)


def _resolve_employee(name):
    """Ищет Employee по ФИО. Возвращает (Employee|None, name_str)."""
    name = (name or '').strip()
    if not name:
        return None, name
    parts = name.split()
    qs = Employee.objects.all()
    if parts:
        qs = qs.filter(last_name__iexact=parts[0])
    if len(parts) >= 2:
        qs = qs.filter(first_name__iexact=parts[1])
    if len(parts) >= 3:
        qs = qs.filter(patronymic__iexact=parts[2])
    emp = qs.first() if parts else None
    if emp and emp.full_name == name:
        return emp, name
    return None, name


def _save_executors(work, executors):
    """Сохраняет список исполнителей задачи."""
    objs = []
    for ex in executors:
        hours = ex.get('hours', {})
        if isinstance(hours, str):
            hours = parse_json_hours(hours)
        emp, name = _resolve_employee(ex.get('name', ''))
        objs.append(
            TaskExecutor(
                work=work,
                executor=emp,
                executor_name=name,
                plan_hours=hours if isinstance(hours, dict) else {},
            )
        )
    if objs:
        TaskExecutor.objects.bulk_create(objs)
