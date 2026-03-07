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
import json
import logging
from datetime import date as dt_date

from django.db import transaction
from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

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
    PRODUCTION_ALLOWED_FIELDS,
    validate_plan_hours,
    validate_executors_list,
    validate_actions,
)
from apps.works.models import (
    Work, TaskWork, TaskExecutor, WorkReport, PPWork, Project, WorkType, AuditLog,
)
from apps.employees.models import Employee, Department, Sector, NTCCenter
from apps.api.audit import log_action

logger = logging.getLogger(__name__)

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
        'id': work.id,
        'task_type': (work.work_type.name if work.work_type else '') or '',
        'dept': (work.department.code if work.department else '') or '',
        'sector': (work.sector.code if work.sector else '') or '',
        'project': (work.project.name if work.project else '') or '',
        'work_name': work.work_name or '',
        'work_number': work.work_number or '',
        'description': work.description or '',
        'executor': (work.executor.full_name if work.executor else
                     work.executor_name_raw) or '',
        'date_start': work.date_start.isoformat() if work.date_start else '',
        'date_end': work.date_end.isoformat() if work.date_end else '',
        'deadline': work.deadline.isoformat() if work.deadline else '',
        'plan_hours': work.plan_hours or {},
        'created_by': work.created_by_id,
        'created_at': work.created_at.isoformat() if work.created_at else '',
        'updated_at': work.updated_at.isoformat() if work.updated_at else '',
        'center': (work.ntc_center.code if work.ntc_center else '') or '',
    }

    # TaskWork-специфичные поля
    if task_detail is None:
        task_detail = getattr(work, '_prefetched_task_detail', None)
        if task_detail is None:
            try:
                task_detail = work.task_detail
            except TaskWork.DoesNotExist:
                task_detail = None

    if task_detail:
        d['stage'] = task_detail.stage or ''
        d['justification'] = task_detail.justification or ''
        d['actions'] = task_detail.actions or {}
    else:
        d['stage'] = ''
        d['justification'] = ''
        d['actions'] = {}

    # Исполнители
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

    # pp_labor из actions
    pp_labor = ''
    if pp_labor_map and work.id in pp_labor_map:
        pp_labor = pp_labor_map[work.id]
    elif isinstance(d['actions'], dict):
        pp_labor = d['actions'].get('pp_labor', '')
    d['pp_labor'] = pp_labor

    # from_pp: задача перенесена из производственного плана
    d['from_pp'] = bool(isinstance(d['actions'], dict) and d['actions'].get('pp_id'))

    return d


# ---------------------------------------------------------------------------
#  GET / POST  /api/tasks
# ---------------------------------------------------------------------------

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
        # Параметры пагинации
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

        # Базовый queryset: только задачи
        qs = Work.objects.filter(source_type=Work.SOURCE_TASK)

        # Видимость по роли
        vis_q = get_visibility_filter(request.user)
        qs = qs.filter(vis_q)

        # Фильтр по году/месяцу
        if year and month:
            try:
                yr = int(year)
                mn = int(month)
                from datetime import date
                sel_start = date(yr, mn, 1)
                if mn < 12:
                    sel_end = date(yr, mn + 1, 1)
                else:
                    sel_end = date(yr + 1, 1, 1)
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

        # Поиск
        if search:
            s = search
            qs = qs.filter(
                Q(work_name__icontains=s)
                | Q(executor__last_name__icontains=s)
                | Q(executor_name_raw__icontains=s)
                | Q(department__code__icontains=s)
                | Q(description__icontains=s)
                | Q(project__name__icontains=s)
                | Q(work_type__name__icontains=s)
                | Q(work_number__icontains=s)
            )

        # Подсчёт до LIMIT/OFFSET
        total_count = qs.count()

        # Сортировка, prefetch и пагинация
        qs = qs.select_related(
            'work_type', 'department', 'sector', 'project',
            'executor', 'ntc_center', 'created_by',
        ).prefetch_related(
            'task_detail', 'task_executors',
        ).order_by('-id')
        qs = qs[offset:offset + limit]

        works = list(qs)

        # Собираем TaskWork и TaskExecutor из prefetch-кэша (0 доп. запросов)
        task_details = {}
        executors_data = {}
        for w in works:
            try:
                td = w.task_detail
                task_details[w.id] = td
            except TaskWork.DoesNotExist:
                pass
            execs = []
            for te in w.task_executors.all():
                execs.append({
                    'name': te.executor_name,
                    'hours': parse_json_hours(te.plan_hours),
                })
            if execs:
                executors_data[w.id] = execs

        # Загрузка pp_labor из связанных ПП
        pp_labor_map = {}
        pp_ids_needed = {}
        for w in works:
            td = task_details.get(w.id)
            if td and isinstance(td.actions, dict):
                pp_id = td.actions.get('pp_id')
                pp_labor_val = td.actions.get('pp_labor')
                if pp_id:
                    if pp_labor_val:
                        pp_labor_map[w.id] = pp_labor_val
                    else:
                        pp_ids_needed[w.id] = pp_id

        if pp_ids_needed:
            pp_id_list = list(set(pp_ids_needed.values()))
            pp_works = PPWork.objects.filter(work_id__in=pp_id_list).values(
                'work_id', 'labor',
            )
            pp_labor_by_id = {
                pw['work_id']: str(pw['labor']) for pw in pp_works
                if pw['labor'] is not None
            }
            for wid, ppid in pp_ids_needed.items():
                if ppid in pp_labor_by_id:
                    pp_labor_map[wid] = pp_labor_by_id[ppid]

        # Формируем результат
        month_key = None
        if year and month:
            try:
                month_key = f"{int(year)}-{int(month):02d}"
            except (ValueError, TypeError):
                month_key = None

        result = []
        for w in works:
            td = task_details.get(w.id)
            execs = executors_data.get(w.id, [])
            d = _serialize_task(w, task_detail=td, executors_data=execs,
                                pp_labor_map=pp_labor_map)
            # plan_hours_month
            if month_key:
                d['plan_hours_month'] = d['plan_hours_all'].get(month_key, '')
            else:
                d['plan_hours_month'] = ''
            result.append(d)

        response = JsonResponse(result, safe=False)
        response['X-Total-Count'] = total_count
        return response


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
        d = parse_json_body(request)
        if not d:
            return JsonResponse({'error': 'Пустое тело запроса'}, status=400)

        employee = getattr(request.user, 'employee', None)

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
                source_type=Work.SOURCE_TASK,
                work_name=d.get('work_name', ''),
                work_number=d.get('work_number', ''),
                description=d.get('description', ''),
                executor_name_raw=d.get('executor', ''),
                plan_hours=ph,
                created_by=employee,
            )

            # FK-поля через текстовое значение (как во Flask)
            _set_work_fk_fields(work, d, request)

            # Даты
            _set_date_fields(work, d)

            work.save()

            TaskWork.objects.create(
                work=work,
                stage=d.get('stage', ''),
                justification=d.get('justification', ''),
                actions=actions,
            )

            if executors_list:
                _save_executors(work, executors_list)

        log_action(request, AuditLog.ACTION_TASK_CREATE,
                   object_id=work.id, object_repr=work.work_name)
        return JsonResponse({'id': work.id})


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/tasks/<id>
# ---------------------------------------------------------------------------

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
            work = Work.objects.filter(
                pk=pk, source_type=Work.SOURCE_TASK
            ).first()
            if not work:
                return JsonResponse({'error': 'Задача не найдена'}, status=404)
            log_action(request, AuditLog.ACTION_TASK_DELETE,
                       object_id=work.id, object_repr=work.work_name)
            work.delete()  # CASCADE удалит TaskWork, TaskExecutor, WorkReport
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error("TaskDetailView.delete error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _update(self, request, pk):
        d = parse_json_body(request)
        if not d:
            return JsonResponse({'error': 'Пустое тело запроса'}, status=400)

        work = Work.objects.filter(
            pk=pk, source_type=Work.SOURCE_TASK
        ).select_related('task_detail').first()
        if not work:
            return JsonResponse({'error': 'Задача не найдена'}, status=404)

        # ------ _mcc_finish: закрытие задачи в конце месяца ------
        if d.get('_mcc_finish'):
            return self._mcc_finish(work)

        # ------ Optimistic locking ------
        if 'updated_at' in d and d['updated_at'] is not None:
            db_updated = str(work.updated_at)
            if db_updated != str(d['updated_at']):
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
            pass
        is_from_pp = bool(
            task_detail and isinstance(task_detail.actions, dict)
            and task_detail.actions.get('pp_id')
        )
        # Для задач, перенесённых из ПП, блокируем изменение ключевых полей
        if is_from_pp and not d.get('_mcc_finish'):
            for lf in ('work_name', 'work_number', 'description',
                       'task_type', 'dept', 'sector', 'project',
                       'stage', 'justification'):
                d.pop(lf, None)

        with transaction.atomic():
            # Обновление plan_hours (частичное или полное)
            if 'plan_hours_update' in d:
                ph_upd, ph_err = validate_plan_hours(d['plan_hours_update'])
                if ph_err:
                    return JsonResponse({'error': ph_err}, status=400)
                existing = parse_json_hours(work.plan_hours)
                existing.update(ph_upd)
                work.plan_hours = existing
                work.save(update_fields=['plan_hours', 'updated_at'])
            else:
                # Полное обновление Work
                if 'plan_hours' in d:
                    ph, ph_err = validate_plan_hours(d.get('plan_hours'))
                    if ph_err:
                        return JsonResponse({'error': ph_err}, status=400)
                else:
                    ph = work.plan_hours
                if not is_from_pp:
                    work.work_name = d.get('work_name', work.work_name)
                    work.work_number = d.get('work_number', work.work_number)
                    work.description = d.get('description', work.description)
                work.executor_name_raw = d.get('executor', work.executor_name_raw)
                work.plan_hours = ph

                _set_work_fk_fields(work, d, request)
                _set_date_fields(work, d)
                work.save()

            # Обновление TaskWork
            try:
                td = work.task_detail
            except TaskWork.DoesNotExist:
                td = TaskWork(work=work)

            if 'stage' in d and not is_from_pp:
                td.stage = d['stage']
            if 'justification' in d and not is_from_pp:
                td.justification = d['justification']
            if 'actions' in d:
                actions, act_err = validate_actions(d['actions'])
                if act_err:
                    return JsonResponse({'error': act_err}, status=400)
                td.actions = actions
            td.save()

            # Обновление исполнителей
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
        """Закрытие задачи: date_end = последний день прошлого месяца,
        plan_hours обрезаются до прошлого месяца."""
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

@method_decorator(csrf_exempt, name='dispatch')
class TaskDeleteAllView(AdminRequiredJsonMixin, View):
    """DELETE /api/tasks/all — удаление всех задач (только admin)."""

    def delete(self, request):
        try:
            with transaction.atomic():
                # CASCADE удалит TaskWork, TaskExecutor
                Work.objects.filter(source_type=Work.SOURCE_TASK).delete()
            logger.info("Администратор очистил все задачи: user=%s",
                        request.user.pk)
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error("TaskDeleteAllView error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  GET /api/tasks/<id>/executors
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class TaskExecutorsView(LoginRequiredJsonMixin, View):
    """GET /api/tasks/<id>/executors — список исполнителей задачи."""

    def get(self, request, pk):
        try:
            executors = TaskExecutor.objects.filter(work_id=pk)
            result = [
                {
                    'name': te.executor_name,
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
    # work_type / task_type
    task_type = d.get('task_type', '')
    if task_type:
        wt, _ = WorkType.objects.get_or_create(name=task_type)
        work.work_type = wt

    # department / dept
    dept = d.get('dept', '')
    if dept:
        dep_obj = Department.objects.filter(code=dept).first()
        if dep_obj:
            work.department = dep_obj

    # sector
    sector = d.get('sector', '')
    if sector and work.department:
        sec_obj = Sector.objects.filter(
            code=sector, department=work.department,
        ).first()
        if sec_obj:
            work.sector = sec_obj

    # project
    project = d.get('project', '')
    if project:
        proj_obj = Project.objects.filter(name=project).first()
        if proj_obj:
            work.project = proj_obj

    # executor (попытка найти Employee по ФИО)
    executor = d.get('executor', '')
    if executor:
        work.executor_name_raw = executor
        emp = Employee.objects.filter(
            Q(last_name__icontains=executor.split()[0])
            if executor.split() else Q()
        ).first()
        if emp and emp.full_name == executor:
            work.executor = emp

    # center (НТЦ)
    employee = getattr(request.user, 'employee', None)
    if employee and employee.ntc_center:
        work.ntc_center = employee.ntc_center


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


def _save_executors(work, executors):
    """Сохраняет список исполнителей задачи."""
    objs = []
    for ex in executors:
        hours = ex.get('hours', {})
        if isinstance(hours, str):
            hours = parse_json_hours(hours)
        objs.append(
            TaskExecutor(
                work=work,
                executor_name=ex.get('name', ''),
                plan_hours=hours if isinstance(hours, dict) else {},
            )
        )
    if objs:
        TaskExecutor.objects.bulk_create(objs)
