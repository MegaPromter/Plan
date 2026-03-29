"""
API сквозного графика.

GET    /api/enterprise/cross/<project_id>/              — сквозной график проекта
POST   /api/enterprise/cross/<project_id>/              — создание сквозного графика
PUT    /api/enterprise/cross/<project_id>/              — обновление (edit_lock, granularity)

POST   /api/enterprise/cross/<project_id>/stages/       — создание этапа
PUT    /api/enterprise/cross_stages/<id>/               — обновление этапа
DELETE /api/enterprise/cross_stages/<id>/               — удаление этапа

POST   /api/enterprise/cross/<project_id>/milestones/   — создание вехи
PUT    /api/enterprise/cross_milestones/<id>/           — обновление вехи
DELETE /api/enterprise/cross_milestones/<id>/           — удаление вехи

GET    /api/enterprise/cross/<project_id>/dept_status/  — статусы отделов
PUT    /api/enterprise/cross_dept_status/<id>/          — обновление статуса отдела
"""
import logging

from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.employees.models import Department
from apps.enterprise.models import (
    CrossMilestone,
    CrossSchedule,
    CrossScheduleDeptStatus,
    CrossStage,
    GeneralSchedule,
    GGStage,
)
from apps.works.models import Project, Work

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Сериализация
# ---------------------------------------------------------------------------

def _serialize_work_brief(w):
    return {
        'id': w.id,
        'name': w.work_name or w.name or '',
        'date_start': str(w.date_start) if w.date_start else None,
        'date_end': str(w.date_end) if w.date_end else None,
        'labor': float(w.labor) if w.labor else None,
        'executor': str(w.executor) if w.executor else '',
        'department': w.department.code if w.department_id else '',
        'row_code': w.row_code or '',
    }


def _serialize_cross_stage(s, works=None):
    d = {
        'id': s.id,
        'name': s.name,
        'date_start': str(s.date_start) if s.date_start else None,
        'date_end': str(s.date_end) if s.date_end else None,
        'department_id': s.department_id,
        'gg_stage_id': s.gg_stage_id,
        'order': s.order,
    }
    if works is not None:
        d['works'] = [_serialize_work_brief(w) for w in works]
        d['works_count'] = len(works)
    return d


def _serialize_cross_milestone(m):
    return {
        'id': m.id,
        'name': m.name,
        'date': str(m.date) if m.date else None,
        'cross_stage_id': m.cross_stage_id,
    }


def _serialize_dept_status(ds):
    return {
        'id': ds.id,
        'department_id': ds.department_id,
        'department_name': ds.department.name if ds.department else '',
        'status': ds.status,
    }


def _serialize_cross_schedule(cs):
    """Полная сериализация сквозного графика."""
    stages = list(cs.stages.select_related('department', 'gg_stage').order_by('order'))
    milestones = list(cs.milestones.select_related('cross_stage').all())
    dept_statuses = list(cs.dept_statuses.select_related('department').all())

    # Работы ПП, привязанные к этапам сквозного графика
    stage_ids = [s.id for s in stages]
    works_qs = (
        Work.objects
        .filter(show_in_pp=True, cross_stage_id__in=stage_ids)
        .select_related('executor', 'department')
        .order_by('id')
    )
    works_by_stage = {}
    for w in works_qs:
        works_by_stage.setdefault(w.cross_stage_id, []).append(w)

    # Неназначенные работы ПП (того же проекта, без cross_stage)
    unassigned_qs = (
        Work.objects
        .filter(
            show_in_pp=True,
            pp_project__up_project_id=cs.project_id,
            cross_stage__isnull=True,
        )
        .select_related('executor', 'department')
        .order_by('id')
    )

    return {
        'id': cs.id,
        'project_id': cs.project_id,
        'version': cs.version,
        'edit_owner': cs.edit_owner,
        'granularity': cs.granularity,
        'created_at': cs.created_at.isoformat(),
        'updated_at': cs.updated_at.isoformat(),
        'stages': [
            _serialize_cross_stage(s, works_by_stage.get(s.id, []))
            for s in stages
        ],
        'milestones': [_serialize_cross_milestone(m) for m in milestones],
        'dept_statuses': [_serialize_dept_status(ds) for ds in dept_statuses],
        'unassigned_works': [_serialize_work_brief(w) for w in unassigned_qs],
    }


# ---------------------------------------------------------------------------
#  Сквозной график
# ---------------------------------------------------------------------------

class CrossScheduleDetailView(LoginRequiredJsonMixin, View):
    """GET/POST/PUT /api/enterprise/cross/<project_id>/"""

    def get(self, request, project_id):
        try:
            cs = CrossSchedule.objects.get(project_id=project_id)
        except CrossSchedule.DoesNotExist:
            return JsonResponse({'schedule': None})
        return JsonResponse({'schedule': _serialize_cross_schedule(cs)})

    def post(self, request, project_id):
        """Создать сквозной график (из ГГ или пустой)."""
        employee = getattr(request.user, 'employee', None)
        if not employee or not employee.is_writer:
            return JsonResponse({'error': 'Нет прав'}, status=403)

        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return JsonResponse({'error': 'Проект не найден'}, status=404)

        if CrossSchedule.objects.filter(project=project).exists():
            return JsonResponse({'error': 'Сквозной график уже существует'}, status=400)

        data = parse_json_body(request) or {}

        cs = CrossSchedule.objects.create(
            project=project,
            created_by=employee,
            granularity=data.get('granularity', 'whole'),
        )

        # Если есть ГГ — копируем этапы оттуда
        if data.get('from_gg', False):
            try:
                gg = GeneralSchedule.objects.get(project=project)
            except GeneralSchedule.DoesNotExist:
                pass
            else:
                for gg_stage in gg.stages.order_by('order'):
                    CrossStage.objects.create(
                        cross_schedule=cs,
                        gg_stage=gg_stage,
                        name=gg_stage.name,
                        date_start=gg_stage.date_start,
                        date_end=gg_stage.date_end,
                        order=gg_stage.order,
                    )

        return JsonResponse({
            'ok': True,
            'schedule': _serialize_cross_schedule(cs),
        }, status=201)

    def put(self, request, project_id):
        """Обновить edit_owner / granularity / version."""
        employee = getattr(request.user, 'employee', None)
        if not employee or not employee.is_writer:
            return JsonResponse({'error': 'Нет прав'}, status=403)

        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            cs = CrossSchedule.objects.get(project_id=project_id)
        except CrossSchedule.DoesNotExist:
            return JsonResponse({'error': 'Сквозной график не найден'}, status=404)

        ALLOWED = {'edit_owner', 'granularity'}
        update_fields = []
        for field in ALLOWED:
            if field in data:
                val = data[field]
                if field == 'edit_owner':
                    valid = [c[0] for c in CrossSchedule.EDIT_OWNER_CHOICES]
                    if val not in valid:
                        return JsonResponse(
                            {'error': f'Недопустимое значение edit_owner: {val}'}, status=400,
                        )
                if field == 'granularity':
                    valid = [c[0] for c in CrossSchedule.GRANULARITY_CHOICES]
                    if val not in valid:
                        return JsonResponse(
                            {'error': f'Недопустимое значение granularity: {val}'}, status=400,
                        )
                setattr(cs, field, val)
                update_fields.append(field)

        if update_fields:
            cs.save(update_fields=update_fields)

        return JsonResponse({'ok': True, 'schedule': _serialize_cross_schedule(cs)})


# ---------------------------------------------------------------------------
#  Этапы сквозного графика
# ---------------------------------------------------------------------------

class CrossStageCreateView(WriterRequiredJsonMixin, View):
    """POST /api/enterprise/cross/<project_id>/stages/"""

    def post(self, request, project_id):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            cs = CrossSchedule.objects.get(project_id=project_id)
        except CrossSchedule.DoesNotExist:
            return JsonResponse({'error': 'Сквозной график не найден'}, status=404)

        # Проверка edit_lock
        if cs.edit_owner == 'locked':
            return JsonResponse({'error': 'График заблокирован'}, status=403)

        name = (data.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'Название обязательно'}, status=400)

        # Валидация FK
        department_id = data.get('department_id')
        if department_id and not Department.objects.filter(pk=department_id).exists():
            return JsonResponse({'error': 'Отдел не найден'}, status=404)

        gg_stage_id = data.get('gg_stage_id')
        if gg_stage_id and not GGStage.objects.filter(pk=gg_stage_id).exists():
            return JsonResponse({'error': 'Этап ГГ не найден'}, status=404)

        max_order = cs.stages.order_by('-order').values_list('order', flat=True).first() or 0

        stage = CrossStage.objects.create(
            cross_schedule=cs,
            name=name,
            date_start=data.get('date_start'),
            date_end=data.get('date_end'),
            department_id=department_id,
            gg_stage_id=gg_stage_id,
            order=data.get('order', max_order + 1),
        )
        return JsonResponse({
            'ok': True,
            'stage': _serialize_cross_stage(stage),
        }, status=201)


class CrossStageDetailView(WriterRequiredJsonMixin, View):
    """PUT/DELETE /api/enterprise/cross_stages/<id>/"""

    def put(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            stage = CrossStage.objects.select_related('cross_schedule').get(pk=pk)
        except CrossStage.DoesNotExist:
            return JsonResponse({'error': 'Этап не найден'}, status=404)

        if stage.cross_schedule.edit_owner == 'locked':
            return JsonResponse({'error': 'График заблокирован'}, status=403)

        # Валидация FK
        if 'department_id' in data and data['department_id']:
            if not Department.objects.filter(pk=data['department_id']).exists():
                return JsonResponse({'error': 'Отдел не найден'}, status=404)
        if 'gg_stage_id' in data and data['gg_stage_id']:
            if not GGStage.objects.filter(pk=data['gg_stage_id']).exists():
                return JsonResponse({'error': 'Этап ГГ не найден'}, status=404)

        FIELDS = ('name', 'date_start', 'date_end', 'department_id', 'gg_stage_id', 'order')
        update_fields = []
        for f in FIELDS:
            if f in data:
                setattr(stage, f, data[f])
                update_fields.append(f)

        if update_fields:
            stage.save(update_fields=update_fields)

        return JsonResponse({'ok': True, 'stage': _serialize_cross_stage(stage)})

    def delete(self, request, pk):
        return JsonResponse(
            {'error': 'Удаление этапов сквозного графика запрещено. Управляйте этапами через ГГ.'},
            status=403,
        )


# ---------------------------------------------------------------------------
#  Вехи сквозного графика
# ---------------------------------------------------------------------------

class CrossMilestoneCreateView(WriterRequiredJsonMixin, View):
    """POST /api/enterprise/cross/<project_id>/milestones/"""

    def post(self, request, project_id):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            cs = CrossSchedule.objects.get(project_id=project_id)
        except CrossSchedule.DoesNotExist:
            return JsonResponse({'error': 'Сквозной график не найден'}, status=404)

        if cs.edit_owner == 'locked':
            return JsonResponse({'error': 'График заблокирован'}, status=403)

        name = (data.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'Название обязательно'}, status=400)

        ms = CrossMilestone.objects.create(
            cross_schedule=cs,
            name=name,
            date=data.get('date'),
            cross_stage_id=data.get('cross_stage_id'),
        )
        return JsonResponse({
            'ok': True,
            'milestone': _serialize_cross_milestone(ms),
        }, status=201)


class CrossMilestoneDetailView(WriterRequiredJsonMixin, View):
    """PUT/DELETE /api/enterprise/cross_milestones/<id>/"""

    def put(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            ms = CrossMilestone.objects.select_related('cross_schedule').get(pk=pk)
        except CrossMilestone.DoesNotExist:
            return JsonResponse({'error': 'Веха не найдена'}, status=404)

        if ms.cross_schedule.edit_owner == 'locked':
            return JsonResponse({'error': 'График заблокирован'}, status=403)

        FIELDS = ('name', 'date', 'cross_stage_id')
        update_fields = []
        for f in FIELDS:
            if f in data:
                setattr(ms, f, data[f])
                update_fields.append(f)

        if update_fields:
            ms.save(update_fields=update_fields)
        return JsonResponse({'ok': True, 'milestone': _serialize_cross_milestone(ms)})

    def delete(self, request, pk):
        try:
            ms = CrossMilestone.objects.select_related('cross_schedule').get(pk=pk)
        except CrossMilestone.DoesNotExist:
            return JsonResponse({'error': 'Веха не найдена'}, status=404)

        if ms.cross_schedule.edit_owner == 'locked':
            return JsonResponse({'error': 'График заблокирован'}, status=403)

        ms.delete()
        return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
#  Статусы отделов
# ---------------------------------------------------------------------------

class CrossDeptStatusListView(LoginRequiredJsonMixin, View):
    """GET /api/enterprise/cross/<project_id>/dept_status/"""

    def get(self, request, project_id):
        try:
            cs = CrossSchedule.objects.get(project_id=project_id)
        except CrossSchedule.DoesNotExist:
            return JsonResponse({'error': 'Сквозной график не найден'}, status=404)

        statuses = cs.dept_statuses.select_related('department').all()
        return JsonResponse({
            'dept_statuses': [_serialize_dept_status(ds) for ds in statuses],
        })


class CrossDeptStatusDetailView(WriterRequiredJsonMixin, View):
    """PUT /api/enterprise/cross_dept_status/<id>/"""

    def put(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            ds = CrossScheduleDeptStatus.objects.get(pk=pk)
        except CrossScheduleDeptStatus.DoesNotExist:
            return JsonResponse({'error': 'Статус не найден'}, status=404)

        status = data.get('status')
        if status:
            valid = [c[0] for c in CrossScheduleDeptStatus.STATUS_CHOICES]
            if status not in valid:
                return JsonResponse(
                    {'error': f'Недопустимый статус: {status}'}, status=400,
                )
            ds.status = status
            ds.save(update_fields=['status'])

        return JsonResponse({'ok': True, 'dept_status': _serialize_dept_status(ds)})


# ---------------------------------------------------------------------------
#  Привязка работ ПП к этапам сквозного графика
# ---------------------------------------------------------------------------

class CrossStageWorksView(WriterRequiredJsonMixin, View):
    """
    POST   /api/enterprise/cross_stages/<id>/works/  — п��ивязать работы
    DELETE /api/enterprise/cross_stages/<id>/works/  — отвязать работы

    Body: { "work_ids": [1, 2, 3] }
    """

    def post(self, request, pk):
        """Привязать работы ПП к этапу сквозного графика."""
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            stage = CrossStage.objects.select_related('cross_schedule').get(pk=pk)
        except CrossStage.DoesNotExist:
            return JsonResponse({'error': 'Этап не найден'}, status=404)

        cs = stage.cross_schedule
        if cs.edit_owner == 'locked':
            return JsonResponse({'error': 'График заблокирован'}, status=403)

        work_ids = data.get('work_ids', [])
        if not work_ids:
            return JsonResponse({'error': 'work_ids обязательно'}, status=400)

        # Проверяем: работы должны быть ПП и принадлежать тому же проекту
        works = Work.objects.filter(
            pk__in=work_ids,
            show_in_pp=True,
            pp_project__up_project_id=cs.project_id,
        )
        if works.count() != len(work_ids):
            return JsonResponse(
                {'error': 'Некоторые работы не найдены или не относятся к этому проекту'},
                status=400,
            )

        works.update(cross_stage=stage)
        return JsonResponse({'ok': True, 'assigned': len(work_ids)})

    def delete(self, request, pk):
        """Отвязать работы от этапа сквозного графика."""
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            stage = CrossStage.objects.select_related('cross_schedule').get(pk=pk)
        except CrossStage.DoesNotExist:
            return JsonResponse({'error': 'Этап не найден'}, status=404)

        cs = stage.cross_schedule
        if cs.edit_owner == 'locked':
            return JsonResponse({'error': 'График заблокирован'}, status=403)

        work_ids = data.get('work_ids', [])
        if not work_ids:
            return JsonResponse({'error': 'work_ids обязательно'}, status=400)

        Work.objects.filter(pk__in=work_ids, cross_stage=stage).update(cross_stage=None)
        return JsonResponse({'ok': True})
