"""
API производственного плана (Work show_in_pp=True).

Аналог Flask-эндпоинтов:
  GET    /api/production_plan        — список записей ПП
  POST   /api/production_plan        — создание записи ПП
  PUT    /api/production_plan/<id>   — обновление записи ПП (inline single-field)
  DELETE /api/production_plan/<id>   — удаление записи ПП
  POST   /api/production_plan/sync   — синхронизация ПП → задачи
"""
import logging
from datetime import date as dt_date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.api.utils import (
    PRODUCTION_ALLOWED_FIELDS, validate_task_type, generate_row_code,
    safe_date, safe_decimal, resolve_employee,
)
from apps.works.models import Work, WorkReport, PPProject, AuditLog
from apps.employees.models import Employee, Department, NTCCenter, Sector
from apps.api.audit import log_action
from apps.api.views.reports import _sync_notices_for_work

logger = logging.getLogger(__name__)

TASKS_MAX = 100000


# ---------------------------------------------------------------------------
#  Вспомогательные функции
# ---------------------------------------------------------------------------

def _round_labor(val):
    """Возвращает целое если значение целое, иначе округляет до 2 знаков."""
    f = float(val)
    i = int(f)
    return i if f == i else round(f, 2)


# _safe_decimal / _safe_date → вынесены в apps.api.utils (safe_decimal / safe_date)
_safe_decimal = safe_decimal
_safe_date = safe_date


# ---------------------------------------------------------------------------
#  Сериализация
# ---------------------------------------------------------------------------

def _serialize_pp(work, today=None):
    """Сериализует Work (show_in_pp=True) в плоский dict для JSON-ответа."""
    if today is None:
        today = timezone.now().date()
    has_reports = getattr(work, '_has_reports', False)
    is_overdue = bool(work.date_end and work.date_end < today and not has_reports)
    return {
        'id': work.id,
        'work_name': work.work_name or '',
        'date_start': work.date_start.isoformat() if work.date_start else '',
        'date_end': work.date_end.isoformat() if work.date_end else '',
        'dept': (work.department.code if work.department else '') or '',
        'center': (work.ntc_center.code if work.ntc_center
                   else (work.department.ntc_center.code
                         if work.department and work.department.ntc_center else '')) or '',
        'executor': (work.executor.full_name if work.executor else '') or '',
        'created_by': work.created_by_id,
        'created_at': work.created_at.isoformat() if work.created_at else '',
        'updated_at': work.updated_at.isoformat() if work.updated_at else '',
        # PP-поля (теперь прямо в Work)
        'row_code': work.row_code or '',
        'work_order': work.work_order or '',
        'stage_num': work.stage_num or '',
        'milestone_num': work.milestone_num or '',
        'work_num': work.work_num or '',
        'work_designation': work.work_designation or '',
        'sheets_a4': float(work.sheets_a4) if work.sheets_a4 is not None else '',
        'norm': float(work.norm) if work.norm is not None else '',
        'coeff': float(work.coeff) if work.coeff is not None else '',
        'total_2d': _round_labor(work.total_2d) if work.total_2d is not None else '',
        'total_3d': _round_labor(work.total_3d) if work.total_3d is not None else '',
        'labor': _round_labor(work.labor) if work.labor is not None else '',
        'sector_head': (work.sector.name or work.sector.code if work.sector else '') or '',
        'task_type': work.task_type or '',
        'project_id': work.pp_project_id,
        'predecessors_count': getattr(work, '_pred_count', 0) or 0,
        'has_reports': has_reports,
        'is_overdue': is_overdue,
    }


# ---------------------------------------------------------------------------
#  Числовые поля (decimal) в Work для ПП
# ---------------------------------------------------------------------------

_PP_DECIMAL_FIELDS = {'sheets_a4', 'norm', 'coeff', 'total_2d', 'total_3d', 'labor'}


# ---------------------------------------------------------------------------
#  GET / POST  /api/production_plan
# ---------------------------------------------------------------------------

class ProductionPlanListView(LoginRequiredJsonMixin, View):
    """GET — список записей ПП."""

    def get(self, request):
        try:
            return self._get_list(request)
        except Exception as e:
            logger.error("ProductionPlanListView.get error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _get_list(self, request):
        try:
            limit = int(request.GET.get('limit', 0)) or TASKS_MAX
        except (ValueError, TypeError):
            limit = TASKS_MAX
        limit = min(limit, TASKS_MAX)

        try:
            offset = max(int(request.GET.get('offset', 0)), 0)
        except (ValueError, TypeError):
            offset = 0

        try:
            project_id = int(request.GET.get('project_id', 0)) or None
        except (ValueError, TypeError):
            project_id = None

        # ПП — общий документ проекта, видимый всем авторизованным пользователям
        qs = Work.objects.filter(show_in_pp=True)

        if project_id:
            qs = qs.filter(pp_project_id=project_id)

        qs = qs.annotate(
            _pred_count=Count('predecessor_links'),
            _has_reports=Exists(WorkReport.objects.filter(work_id=OuterRef('pk'))),
        ).select_related(
            'department', 'department__ntc_center', 'ntc_center',
            'executor', 'sector', 'pp_project',
        ).order_by('id')

        # Общее количество (до пагинации) — для клиента
        total_count = qs.count()

        qs = qs[offset:offset + limit]
        works = list(qs)
        today = timezone.now().date()

        resp = JsonResponse([_serialize_pp(w, today) for w in works], safe=False)
        resp['X-Total-Count'] = total_count
        return resp


class ProductionPlanCreateView(WriterRequiredJsonMixin, View):
    """POST /api/production_plan — создание записи ПП."""

    def post(self, request):
        try:
            return self._create(request)
        except Exception as e:
            logger.error("ProductionPlanCreateView error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _create(self, request):
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        project_id = d.get('project_id') or None
        if not project_id:
            return JsonResponse(
                {'error': 'Необходимо выбрать проект ПП перед добавлением строки'},
                status=400,
            )
        employee = getattr(request.user, 'employee', None)

        # Проверка прав на отдел/сектор
        if employee and employee.role in ('dept_head', 'dept_deputy'):
            if not employee.department:
                return JsonResponse({'error': 'Вашему профилю не назначен отдел'}, status=403)
            dept_code = d.get('dept', '') or ''
            if dept_code and dept_code != employee.department.code:
                return JsonResponse(
                    {'error': 'Вы можете создавать задачи только для своего отдела'},
                    status=403,
                )
        elif employee and employee.role == 'sector_head':
            if not employee.department:
                return JsonResponse({'error': 'Вашему профилю не назначен отдел'}, status=403)
            dept_code = d.get('dept', '') or ''
            if dept_code and dept_code != employee.department.code:
                return JsonResponse(
                    {'error': 'Вы можете создавать задачи только для своего отдела'},
                    status=403,
                )
            sector_head_val = (d.get('sector_head') or '').strip()
            if sector_head_val and employee.sector:
                own_sector_values = {employee.sector.code, employee.sector.name}
                if sector_head_val not in own_sector_values:
                    return JsonResponse(
                        {'error': 'Вы можете создавать задачи только для своего сектора'},
                        status=403,
                    )

        ntc_center = (employee.effective_ntc_center if employee else None)

        dept_obj = None
        if employee and employee.role in ('dept_head', 'dept_deputy', 'sector_head'):
            dept_obj = employee.department
        elif d.get('dept'):
            dept_obj = Department.objects.filter(code=d['dept']).first()

        _validated_tt, tt_err = validate_task_type(d.get('task_type', ''))
        if tt_err:
            return JsonResponse({'error': tt_err}, status=400)
        if not _validated_tt:
            _validated_tt = 'Выпуск нового документа'

        with transaction.atomic():
            work = Work.objects.create(
                show_in_pp=True,
                work_name=d.get('work_name', '') or '',
                task_type=_validated_tt,
                pp_project_id=project_id,
                ntc_center=ntc_center,
                department=dept_obj,
                created_by=employee,
            )

            # Автогенерация row_code
            up_project = work.pp_project.up_project if work.pp_project else None
            if up_project:
                work.row_code = generate_row_code(up_project)
                if work.row_code:
                    work.save(update_fields=['row_code'])
                else:
                    logger.warning(
                        "row_code не сгенерирован для work=%s, project=%s",
                        work.pk, up_project.pk,
                    )

            # Применяем остальные поля без промежуточных save()
            detail_view = ProductionPlanDetailView()
            changed = False
            for field in PRODUCTION_ALLOWED_FIELDS:
                if field in ('work_name', 'task_type'):
                    continue
                value = d.get(field)
                if value is None or value == '':
                    continue
                detail_view._update_field(work, field, value, save=False)
                changed = True
            if changed:
                work.save()

            # Синхронизация ЖИ при создании с task_type «Корректировка документа»
            _sync_notices_for_work(work)

        log_action(request, AuditLog.ACTION_PP_CREATE,
                   object_id=work.pk,
                   object_repr=work.work_name or str(work.pk),
                   details={'task_type': work.task_type})

        work_data = _serialize_pp(
            Work.objects.annotate(
                _pred_count=Count('predecessor_links'),
                _has_reports=Exists(WorkReport.objects.filter(work_id=OuterRef('pk'))),
            ).select_related('department', 'ntc_center', 'executor', 'sector', 'pp_project')
            .get(pk=work.pk)
        )
        return JsonResponse({'id': work.id, 'work': work_data})


# ---------------------------------------------------------------------------
#  Вспомогательная проверка прав на редактирование записи ПП
# ---------------------------------------------------------------------------

def _check_dept_access(user, work):
    """
    Проверяет, может ли пользователь редактировать/удалять запись ПП.
    Admin — может всё. Остальные — только записи своего отдела.
    Возвращает строку с ошибкой или None если доступ разрешён.
    """
    employee = getattr(user, 'employee', None)
    if not employee:
        return 'Нет профиля сотрудника'
    # Администратор и руководство НТЦ редактируют любые записи
    if employee.role in ('admin', 'ntc_head', 'ntc_deputy'):
        return None
    # Начальники отделов/секторов — только свой отдел
    if not employee.department:
        return 'Вашему профилю не назначен отдел'
    if work.department and employee.department_id != work.department_id:
        return 'Вы можете редактировать только записи своего отдела'
    return None


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/production_plan/<id>
# ---------------------------------------------------------------------------

class ProductionPlanDetailView(WriterRequiredJsonMixin, View):
    """PUT /api/production_plan/<id>; DELETE /api/production_plan/<id>."""

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except Exception as e:
            logger.error("ProductionPlanDetailView.put error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def delete(self, request, pk):
        try:
            with transaction.atomic():
                work = (Work.objects.select_for_update(of=('self',))
                        .filter(pk=pk, show_in_pp=True)
                        .select_related('department').first())
                if not work:
                    return JsonResponse({'error': 'Запись ПП не найдена'}, status=404)
                # Проверка: не-admin может удалять только записи своего отдела
                err = _check_dept_access(request.user, work)
                if err:
                    return JsonResponse({'error': err}, status=403)
                work_repr = f'{work.work_name} (id={work.pk})'
                if work.show_in_plan:
                    # Запись также видна в СП — не удаляем, а убираем из ПП
                    work.show_in_pp = False
                    work.pp_project = None
                    work.save(update_fields=['show_in_pp', 'pp_project'])
                else:
                    work.delete()
                log_action(request, AuditLog.ACTION_PP_DELETE,
                           object_id=pk,
                           object_repr=work_repr)
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error("ProductionPlanDetailView.delete error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _update(self, request, pk):
        """Inline single-field update."""
        field = request.GET.get('field')
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        value = d.get('value', '')

        if not field:
            return JsonResponse({'error': 'field parameter required'}, status=400)
        if field not in PRODUCTION_ALLOWED_FIELDS:
            return JsonResponse({'error': f'Недопустимое поле: {field}'}, status=400)

        if field == 'task_type':
            value, tt_err = validate_task_type(value)
            if tt_err:
                return JsonResponse({'error': tt_err}, status=400)
            if not value:
                value = 'Выпуск нового документа'

        with transaction.atomic():
            work = (Work.objects.select_for_update(of=('self',))
                    .filter(pk=pk, show_in_pp=True)
                    .select_related('department', 'ntc_center', 'executor', 'sector')
                    .first())
            if not work:
                return JsonResponse({'error': 'Запись ПП не найдена'}, status=404)

            # Проверка: не-admin может редактировать только записи своего отдела
            err = _check_dept_access(request.user, work)
            if err:
                return JsonResponse({'error': err}, status=403)

            # Optimistic locking — нормализуем оба timestamp до YYYY-MM-DDTHH:MM:SS
            client_updated_at = d.get('updated_at')
            if client_updated_at is not None:
                server_ts = (work.updated_at.strftime('%Y-%m-%dT%H:%M:%S')
                             if work.updated_at else '')
                raw = str(client_updated_at).replace(' ', 'T')
                client_ts = raw[:19] if len(raw) >= 19 else raw
                if server_ts != client_ts:
                    return JsonResponse({
                        'error': 'conflict',
                        'message': 'Запись была изменена другим пользователем. '
                                   'Перезагрузите данные.',
                    }, status=409)

            self._update_field(work, field, value)
            log_action(request, AuditLog.ACTION_PP_UPDATE,
                       object_id=work.pk,
                       object_repr=work.work_name or str(work.pk),
                       details={'field': field, 'value': str(value)[:200]})

        return JsonResponse({'ok': True})

    def _update_field(self, work, field, value, save=True):
        """Обновляет одно поле в Work."""
        if field == 'work_name':
            work.work_name = value or ''
        elif field == 'date_start':
            work.date_start = _safe_date(value)
        elif field == 'date_end':
            work.date_end = _safe_date(value)
        elif field == 'executor':
            # Строгий поиск по ФИО — назначаем только при точном совпадении
            if value:
                emp, _ = resolve_employee(value)
                work.executor = emp
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
        elif field in _PP_DECIMAL_FIELDS:
            setattr(work, field, _safe_decimal(value))
        elif field == 'sector_head':
            # sector_head теперь устанавливается через FK sector
            if value:
                sec = Sector.objects.filter(
                    Q(code=value) | Q(name=value),
                    department=work.department,
                ).first() if work.department else Sector.objects.filter(
                    Q(code=value) | Q(name=value),
                ).first()
                work.sector = sec
            else:
                work.sector = None
        elif field == 'task_type':
            work.task_type = value or ''
        else:
            # row_code, work_order, stage_num, milestone_num, work_num, work_designation
            setattr(work, field, value or '')
        if save:
            work.save()
            # Синхронизация ЖИ при смене task_type
            if field == 'task_type':
                _sync_notices_for_work(work)


# ---------------------------------------------------------------------------
#  POST /api/production_plan/sync
# ---------------------------------------------------------------------------

class ProductionPlanSyncView(WriterRequiredJsonMixin, View):
    """POST /api/production_plan/sync — синхронизация ПП → СП.

    Никаких копий/дублей: просто включает show_in_plan=True на записях ПП,
    чтобы они стали видны в модуле «План/отчёт».
    Сериализатор _serialize_task сам маппит ПП-поля в СП-колонки.
    """

    def post(self, request):
        try:
            return self._sync(request)
        except Exception as e:
            logger.error("ProductionPlanSyncView error: %s", e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def _sync(self, request):
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        filter_project_id = d.get('project_id') or None
        if not filter_project_id:
            return JsonResponse(
                {'error': 'Необходимо указать project_id для синхронизации'},
                status=400,
            )

        # Проверка прав: только admin/ntc_head/ntc_deputy или writer своего отдела
        employee = getattr(request.user, 'employee', None)
        if not employee:
            return JsonResponse({'error': 'Нет профиля сотрудника'}, status=403)

        # Непустые ПП-записи проекта, ещё не показанные в СП
        qs = Work.objects.filter(
            show_in_pp=True,
            show_in_plan=False,
            pp_project_id=filter_project_id,
        )

        # Ограничение по отделу: не-admin/ntc видят только свой отдел
        if employee.role not in ('admin', 'ntc_head', 'ntc_deputy'):
            if not employee.department:
                return JsonResponse({'error': 'Вашему профилю не назначен отдел'}, status=403)
            qs = qs.filter(department=employee.department)

        # Если переданы конкретные ids (отфильтрованные на клиенте) — синхронизируем только их
        ids = d.get('ids')
        if ids and isinstance(ids, list):
            qs = qs.filter(pk__in=ids)

        # Включаем show_in_plan одним запросом
        synced = qs.update(show_in_plan=True)

        log_action(request, AuditLog.ACTION_PP_SYNC,
                   details={'synced': synced})
        return JsonResponse({'synced': synced})
