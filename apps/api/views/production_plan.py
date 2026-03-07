"""
API производственного плана (Work source_type='pp' + PPWork).

Аналог Flask-эндпоинтов:
  GET    /api/production_plan        — список записей ПП
  POST   /api/production_plan        — создание записи ПП
  PUT    /api/production_plan/<id>   — обновление записи ПП (inline single-field)
  DELETE /api/production_plan/<id>   — удаление записи ПП
  POST   /api/production_plan/sync   — синхронизация ПП → задачи
"""
import json
import logging
from datetime import date as dt_date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.api.utils import (
    get_visibility_filter,
    PRODUCTION_ALLOWED_FIELDS,
)
from apps.works.models import (
    Work, TaskWork, PPWork, PPProject, AuditLog,
)
from apps.employees.models import Employee, Department, NTCCenter
from apps.api.audit import log_action

logger = logging.getLogger(__name__)

TASKS_MAX = 500


# ---------------------------------------------------------------------------
#  Вспомогательные функции
# ---------------------------------------------------------------------------

def _round_labor(val):
    """Возвращает целое если значение целое, иначе округляет до 2 знаков."""
    f = float(val)
    i = int(f)
    return i if f == i else round(f, 2)


# ---------------------------------------------------------------------------
#  Сериализация
# ---------------------------------------------------------------------------

def _serialize_pp(work, pp_detail=None):
    """Сериализует Work + PPWork в плоский dict для JSON-ответа."""
    if pp_detail is None:
        try:
            pp_detail = work.pp_detail
        except PPWork.DoesNotExist:
            pp_detail = None

    d = {
        'id': work.id,
        'work_name': work.work_name or '',
        'date_start': work.date_start.isoformat() if work.date_start else '',
        'date_end': work.date_end.isoformat() if work.date_end else '',
        'dept': (work.department.code if work.department else '') or '',
        'center': (work.ntc_center.code if work.ntc_center else '') or '',
        'executor': (work.executor.full_name if work.executor else
                     work.executor_name_raw) or '',
        'created_by': work.created_by_id,
        'created_at': work.created_at.isoformat() if work.created_at else '',
        'updated_at': work.updated_at.isoformat() if work.updated_at else '',
    }

    if pp_detail:
        d.update({
            'row_code': pp_detail.row_code or '',
            'work_order': pp_detail.work_order or '',
            'stage_num': pp_detail.stage_num or '',
            'milestone_num': pp_detail.milestone_num or '',
            'work_num': pp_detail.work_num or '',
            'work_designation': pp_detail.work_designation or '',
            'sheets_a4': (float(pp_detail.sheets_a4)
                          if pp_detail.sheets_a4 is not None else ''),
            'norm': (float(pp_detail.norm)
                     if pp_detail.norm is not None else ''),
            'coeff': (float(pp_detail.coeff)
                      if pp_detail.coeff is not None else ''),
            'total_2d': (_round_labor(pp_detail.total_2d)
                         if pp_detail.total_2d is not None else ''),
            'total_3d': (_round_labor(pp_detail.total_3d)
                         if pp_detail.total_3d is not None else ''),
            'labor': (_round_labor(pp_detail.labor)
                      if pp_detail.labor is not None else ''),
            'sector_head': pp_detail.sector_head_name or '',
            'task_type': pp_detail.task_type or '',
            'project_id': pp_detail.pp_project_id,
        })
    else:
        d.update({
            'row_code': '', 'work_order': '', 'stage_num': '',
            'milestone_num': '', 'work_num': '', 'work_designation': '',
            'sheets_a4': '', 'norm': '', 'coeff': '',
            'total_2d': '', 'total_3d': '', 'labor': '',
            'sector_head': '', 'task_type': '', 'project_id': None,
        })

    return d


# ---------------------------------------------------------------------------
#  Маппинг полей для inline-обновления
# ---------------------------------------------------------------------------

# Поля, хранящиеся в Work
_WORK_FIELDS = {'work_name', 'date_start', 'date_end', 'executor', 'dept',
                'center'}
# Поля, хранящиеся в PPWork
_PP_FIELDS = {
    'row_code', 'work_order', 'stage_num', 'milestone_num', 'work_num',
    'work_designation', 'sheets_a4', 'norm', 'coeff', 'total_2d',
    'total_3d', 'labor', 'sector_head', 'task_type',
}

# Числовые decimal-поля в PPWork
_PP_DECIMAL_FIELDS = {'sheets_a4', 'norm', 'coeff', 'total_2d', 'total_3d',
                      'labor'}


def _safe_decimal(val):
    if val is None or val == '':
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_date(val):
    if not val or val == '':
        return None
    try:
        return dt_date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
#  GET / POST  /api/production_plan
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class ProductionPlanListView(LoginRequiredJsonMixin, View):
    """GET — список записей ПП; POST — создание записи ПП."""

    def get(self, request):
        try:
            return self._get_list(request)
        except Exception as e:
            logger.error("ProductionPlanListView.get error: %s", e,
                         exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def _get_list(self, request):
        try:
            limit = int(request.GET.get('limit', 0)) or TASKS_MAX
        except (ValueError, TypeError):
            limit = TASKS_MAX
        limit = min(limit, TASKS_MAX)

        try:
            offset = int(request.GET.get('offset', 0))
        except (ValueError, TypeError):
            offset = 0

        try:
            project_id = int(request.GET.get('project_id', 0)) or None
        except (ValueError, TypeError):
            project_id = None

        qs = Work.objects.filter(source_type=Work.SOURCE_PP)

        # Видимость по роли
        vis_q = get_visibility_filter(request.user)
        qs = qs.filter(vis_q)

        # Фильтр по проекту ПП
        if project_id:
            qs = qs.filter(pp_detail__pp_project_id=project_id)

        qs = qs.select_related(
            'department', 'ntc_center', 'executor', 'pp_detail',
            'pp_detail__pp_project',
        ).order_by('id')

        qs = qs[offset:offset + limit]
        works = list(qs)

        result = []
        for w in works:
            pp_detail = getattr(w, 'pp_detail', None)
            result.append(_serialize_pp(w, pp_detail))

        return JsonResponse(result, safe=False)


@method_decorator(csrf_exempt, name='dispatch')
class ProductionPlanCreateView(WriterRequiredJsonMixin, View):
    """POST /api/production_plan — создание записи ПП."""

    def post(self, request):
        try:
            return self._create(request)
        except Exception as e:
            logger.error("ProductionPlanCreateView error: %s", e,
                         exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def _create(self, request):
        d = parse_json_body(request)
        project_id = d.get('project_id') or None
        employee = getattr(request.user, 'employee', None)

        # НТЦ-центр из профиля пользователя (может быть перезаписан полем 'center')
        ntc_center = employee.ntc_center if employee and employee.ntc_center else None

        with transaction.atomic():
            work = Work.objects.create(
                source_type=Work.SOURCE_PP,
                work_name=d.get('work_name', '') or '',
                ntc_center=ntc_center,
                created_by=employee,
            )
            pp = PPWork.objects.create(
                work=work,
                task_type=d.get('task_type', '') or 'Выпуск нового документа',
                pp_project_id=project_id,
                created_by=request.user,
            )

        # Применяем все остальные поля через те же методы что и PUT
        detail_view = ProductionPlanDetailView()
        for field in PRODUCTION_ALLOWED_FIELDS:
            if field in ('work_name', 'task_type'):
                continue  # уже применены выше
            value = d.get(field)
            if value is None or value == '':
                continue
            if field in _WORK_FIELDS:
                detail_view._update_work_field(work, field, value)
            elif field in _PP_FIELDS:
                detail_view._update_pp_field(work, field, value)

        return JsonResponse({'id': work.id})


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/production_plan/<id>
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class ProductionPlanDetailView(WriterRequiredJsonMixin, View):
    """PUT /api/production_plan/<id>; DELETE /api/production_plan/<id>."""

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except Exception as e:
            logger.error("ProductionPlanDetailView.put error: %s", e,
                         exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def delete(self, request, pk):
        try:
            work = Work.objects.filter(
                pk=pk, source_type=Work.SOURCE_PP,
            ).first()
            if not work:
                return JsonResponse(
                    {'error': 'Запись ПП не найдена'}, status=404,
                )
            work.delete()  # CASCADE удалит PPWork
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error("ProductionPlanDetailView.delete error: %s", e,
                         exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def _update(self, request, pk):
        """Inline single-field update (аналог Flask update_production_task)."""
        field = request.GET.get('field')
        d = parse_json_body(request)
        value = d.get('value', '')

        if not field:
            return JsonResponse(
                {'error': 'field parameter required'}, status=400,
            )
        if field not in PRODUCTION_ALLOWED_FIELDS:
            return JsonResponse(
                {'error': f'Недопустимое поле: {field}'}, status=400,
            )

        # Тип задачи — дефолт если пустой
        if field == 'task_type' and not str(value).strip():
            value = 'Выпуск нового документа'

        work = Work.objects.filter(
            pk=pk, source_type=Work.SOURCE_PP,
        ).select_related('pp_detail').first()
        if not work:
            return JsonResponse(
                {'error': 'Запись ПП не найдена'}, status=404,
            )

        # Optimistic locking
        client_updated_at = d.get('updated_at')
        if client_updated_at:
            if str(work.updated_at) != str(client_updated_at):
                return JsonResponse({
                    'error': 'conflict',
                    'message': 'Запись была изменена другим пользователем. '
                               'Перезагрузите данные.',
                }, status=409)

        with transaction.atomic():
            if field in _WORK_FIELDS:
                self._update_work_field(work, field, value)
            elif field in _PP_FIELDS:
                self._update_pp_field(work, field, value)

        return JsonResponse({'ok': True})

    def _update_work_field(self, work, field, value):
        """Обновляет поле, хранящееся в Work."""
        if field == 'work_name':
            work.work_name = value or ''
        elif field == 'date_start':
            work.date_start = _safe_date(value)
        elif field == 'date_end':
            work.date_end = _safe_date(value)
        elif field == 'executor':
            work.executor_name_raw = value or ''
            # Попытка привязать к Employee
            if value:
                emp = Employee.objects.filter(
                    last_name__icontains=value.split()[0]
                ).first() if value.split() else None
                if emp and emp.full_name == value:
                    work.executor = emp
                else:
                    work.executor = None
            else:
                work.executor = None
        elif field == 'dept':
            if value:
                dep = Department.objects.filter(code=value).first()
                work.department = dep
            else:
                work.department = None
        elif field == 'center':
            if value:
                center = NTCCenter.objects.filter(code=value).first()
                work.ntc_center = center
            else:
                work.ntc_center = None
        work.save()

    def _update_pp_field(self, work, field, value):
        """Обновляет поле, хранящееся в PPWork."""
        try:
            pp = work.pp_detail
        except PPWork.DoesNotExist:
            pp = PPWork(work=work)

        if field in _PP_DECIMAL_FIELDS:
            setattr(pp, field, _safe_decimal(value))
        elif field == 'sector_head':
            pp.sector_head_name = value or ''
        else:
            setattr(pp, field, value or '')
        pp.save()


# ---------------------------------------------------------------------------
#  POST /api/production_plan/sync
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class ProductionPlanSyncView(LoginRequiredJsonMixin, View):
    """POST /api/production_plan/sync — синхронизация ПП в задачи."""

    def post(self, request):
        try:
            return self._sync(request)
        except Exception as e:
            logger.error("ProductionPlanSyncView error: %s", e, exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def _sync(self, request):
        d = parse_json_body(request)
        filter_project_id = d.get('project_id') or None
        employee = getattr(request.user, 'employee', None)

        # 1. Получаем записи ПП
        pp_qs = Work.objects.filter(
            source_type=Work.SOURCE_PP,
        ).select_related(
            'pp_detail', 'pp_detail__pp_project',
            'department', 'executor',
        )
        if filter_project_id:
            pp_qs = pp_qs.filter(pp_detail__pp_project_id=filter_project_id)
        pp_qs = pp_qs.order_by('id')

        pp_works = list(pp_qs)

        # 2. Найти существующие задачи, привязанные к ПП через actions.pp_id
        #    Используем values() — не создаём ORM-объекты, только нужные поля
        existing_pp_map = {}  # pp_work_id -> task Work.id
        for row in TaskWork.objects.filter(
            work__source_type=Work.SOURCE_TASK,
        ).exclude(actions={}).exclude(actions__isnull=True).values('work_id', 'actions'):
            actions = row['actions']
            if isinstance(actions, dict):
                pp_id = actions.get('pp_id')
                if pp_id is not None:
                    existing_pp_map[pp_id] = row['work_id']

        # Колонки для проверки «пустая ли строка ПП»
        _check_fields_pp = [
            'row_code', 'work_order', 'stage_num', 'milestone_num',
            'work_num', 'work_designation', 'work_name',
        ]
        _check_fields_pp_decimal = [
            'sheets_a4', 'norm', 'coeff', 'total_2d', 'total_3d', 'labor',
        ]

        imported = 0
        updated = 0

        with transaction.atomic():
            tasks_to_create = []
            task_details_to_create = []
            update_tasks = []  # (work_id, date_start, deadline)

            for pp_work in pp_works:
                pp_detail = getattr(pp_work, 'pp_detail', None)
                if not pp_detail:
                    continue

                # Пропускаем полностью пустые строки
                is_empty = True
                for c in _check_fields_pp:
                    val = str(getattr(pp_detail, c, '') or '').strip()
                    if val:
                        is_empty = False
                        break
                if is_empty:
                    if pp_work.work_name and pp_work.work_name.strip():
                        is_empty = False
                if is_empty:
                    for c in _check_fields_pp_decimal:
                        val = getattr(pp_detail, c, None)
                        if val is not None:
                            is_empty = False
                            break
                if is_empty:
                    # Проверяем Work-уровневые поля
                    if pp_work.date_end or pp_work.executor or \
                            pp_work.executor_name_raw or \
                            (pp_work.department and pp_work.department.code) or \
                            (pp_work.ntc_center and pp_work.ntc_center.code) or \
                            (pp_detail.sector_head_name or '').strip() or \
                            (pp_detail.task_type or '').strip():
                        is_empty = False
                if is_empty:
                    continue

                if pp_work.id in existing_pp_map:
                    # Обновляем date_start и deadline существующей задачи
                    task_work_id = existing_pp_map[pp_work.id]
                    update_tasks.append((
                        task_work_id,
                        pp_work.date_start,
                        pp_work.date_end,
                    ))
                    continue

                # --- Создаём новую задачу из ПП ---
                # Обоснование = название ПП-плана + номера этапа/вехи/работы
                pp_plan_name = ''
                if pp_detail.pp_project:
                    pp_plan_name = pp_detail.pp_project.name or ''
                stage_num    = pp_detail.stage_num or ''
                milestone    = pp_detail.milestone_num or ''
                work_num     = pp_detail.work_num or ''
                parts = [pp_plan_name] if pp_plan_name else []
                if stage_num:
                    parts.append(f'Этап {stage_num}')
                if milestone:
                    parts.append(f'Веха {milestone}')
                if work_num:
                    parts.append(f'Работа {work_num}')
                justification = '; '.join(parts)

                task_type_str = pp_detail.task_type or 'выпуск документа'
                executor_name = ''
                executor_fk = None
                if pp_work.executor:
                    executor_name = pp_work.executor.full_name
                    executor_fk = pp_work.executor
                elif pp_work.executor_name_raw:
                    executor_name = pp_work.executor_name_raw

                pp_labor_val = ''
                if pp_detail.labor is not None:
                    pp_labor_val = str(float(pp_detail.labor))

                # Work-тип для work_type FK
                from apps.works.models import WorkType
                wt = None
                if task_type_str:
                    wt, _ = WorkType.objects.get_or_create(name=task_type_str)

                new_work = Work(
                    source_type=Work.SOURCE_TASK,
                    work_type=wt,
                    department=pp_work.department,
                    work_name=pp_work.work_name or '',
                    work_number=pp_detail.work_designation or '',
                    executor=executor_fk,
                    executor_name_raw=executor_name,
                    date_start=pp_work.date_start,
                    # date_end НЕ переносим — заполняет пользователь
                    deadline=pp_work.date_end,  # deadline = date_end из ПП
                    created_by=employee,
                )
                new_work.save()

                new_td = TaskWork(
                    work=new_work,
                    stage=pp_detail.stage_num or '',
                    justification=justification,
                    actions={
                        'pp_id': pp_work.id,
                        'pp_labor': pp_labor_val,
                    },
                )
                new_td.save()

                imported += 1

            # Обновляем даты существующих задач
            for task_wid, ds, deadline in update_tasks:
                Work.objects.filter(pk=task_wid).update(
                    date_start=ds,
                    deadline=deadline,
                )
                updated += 1

        log_action(request, AuditLog.ACTION_PP_SYNC,
                   details={'imported': imported, 'updated': updated})
        return JsonResponse({'imported': imported, 'updated': updated})
