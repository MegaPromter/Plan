"""
API генерального графика (ГГ).

GET    /api/enterprise/gg/<project_id>/           — ГГ проекта (этапы, вехи)
POST   /api/enterprise/gg/<project_id>/           — создание ГГ (из шаблона или пустой)
PUT    /api/enterprise/gg/<project_id>/           — обновление метаданных ГГ

GET    /api/enterprise/gg_templates/               — список шаблонов ГГ
POST   /api/enterprise/gg_templates/               — создание шаблона
DELETE /api/enterprise/gg_templates/<id>/           — удаление шаблона

POST   /api/enterprise/gg/<project_id>/stages/     — создание этапа
PUT    /api/enterprise/gg_stages/<id>/             — обновление этапа
DELETE /api/enterprise/gg_stages/<id>/             — удаление этапа

POST   /api/enterprise/gg/<project_id>/milestones/ — создание вехи
PUT    /api/enterprise/gg_milestones/<id>/         — обновление вехи
DELETE /api/enterprise/gg_milestones/<id>/         — удаление вехи

POST   /api/enterprise/gg_stage_deps/              — создание зависимости
DELETE /api/enterprise/gg_stage_deps/<id>/          — удаление зависимости
"""
import logging

from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    AdminRequiredJsonMixin,
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.enterprise.models import (
    CrossStage,
    GeneralSchedule,
    GGMilestone,
    GGStage,
    GGStageDependency,
    GGTemplate,
    GGTemplateStage,
)
from apps.works.models import Project

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Сериализация
# ---------------------------------------------------------------------------

def _serialize_stage(s):
    return {
        'id': s.id,
        'name': s.name,
        'date_start': str(s.date_start) if s.date_start else None,
        'date_end': str(s.date_end) if s.date_end else None,
        'labor': float(s.labor) if s.labor else None,
        'order': s.order,
        'parent_stage_id': s.parent_stage_id,
    }


def _serialize_milestone(m):
    return {
        'id': m.id,
        'name': m.name,
        'date': str(m.date) if m.date else None,
        'stage_id': m.stage_id,
    }


def _serialize_dependency(d):
    return {
        'id': d.id,
        'predecessor_id': d.predecessor_id,
        'successor_id': d.successor_id,
        'dep_type': d.dep_type,
        'lag_days': d.lag_days,
    }


def _serialize_gg(schedule):
    """Полная сериализация ГГ с этапами, вехами и зависимостями."""
    stages = list(schedule.stages.select_related('parent_stage').order_by('order'))
    milestones = list(schedule.milestones.select_related('stage').all())
    stage_ids = [s.id for s in stages]
    deps = list(GGStageDependency.objects.filter(
        predecessor_id__in=stage_ids,
    ))

    return {
        'id': schedule.id,
        'project_id': schedule.project_id,
        'created_at': schedule.created_at.isoformat(),
        'updated_at': schedule.updated_at.isoformat(),
        'stages': [_serialize_stage(s) for s in stages],
        'milestones': [_serialize_milestone(m) for m in milestones],
        'dependencies': [_serialize_dependency(d) for d in deps],
    }


# ---------------------------------------------------------------------------
#  ГГ проекта
# ---------------------------------------------------------------------------

class GGDetailView(LoginRequiredJsonMixin, View):
    """GET/POST/PUT /api/enterprise/gg/<project_id>/"""

    def get(self, request, project_id):
        """Получить ГГ проекта."""
        try:
            schedule = GeneralSchedule.objects.get(project_id=project_id)
        except GeneralSchedule.DoesNotExist:
            return JsonResponse({'schedule': None})
        return JsonResponse({'schedule': _serialize_gg(schedule)})

    def post(self, request, project_id):
        """Создать ГГ (опционально из шаблона)."""
        # WriterRequired проверяется вручную
        employee = getattr(request.user, 'employee', None)
        if not employee or not employee.is_writer:
            return JsonResponse({'error': 'Нет прав'}, status=403)

        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return JsonResponse({'error': 'Проект не найден'}, status=404)

        if GeneralSchedule.objects.filter(project=project).exists():
            return JsonResponse({'error': 'ГГ уже существует'}, status=400)

        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        schedule = GeneralSchedule.objects.create(
            project=project,
            created_by=employee,
        )

        # Если указан шаблон — копируем этапы
        template_id = data.get('template_id')
        if template_id:
            try:
                template = GGTemplate.objects.get(pk=template_id)
            except GGTemplate.DoesNotExist:
                return JsonResponse({'error': 'Шаблон не найден'}, status=404)

            for ts in template.stages.order_by('order'):
                GGStage.objects.create(
                    schedule=schedule,
                    name=ts.name,
                    order=ts.order,
                )

        return JsonResponse({
            'ok': True,
            'schedule': _serialize_gg(schedule),
        }, status=201)

    def put(self, request, project_id):
        """Обновить ГГ (пока заглушка для метаданных)."""
        employee = getattr(request.user, 'employee', None)
        if not employee or not employee.is_writer:
            return JsonResponse({'error': 'Нет прав'}, status=403)

        try:
            schedule = GeneralSchedule.objects.get(project_id=project_id)
        except GeneralSchedule.DoesNotExist:
            return JsonResponse({'error': 'ГГ не найден'}, status=404)

        schedule.save(update_fields=['updated_at'])
        return JsonResponse({'ok': True, 'schedule': _serialize_gg(schedule)})


# ---------------------------------------------------------------------------
#  Шаблоны ГГ
# ---------------------------------------------------------------------------

class GGTemplateListView(LoginRequiredJsonMixin, View):
    """GET/POST /api/enterprise/gg_templates/"""

    def get(self, request):
        templates = GGTemplate.objects.prefetch_related('stages').order_by('name')
        result = []
        for t in templates:
            result.append({
                'id': t.id,
                'name': t.name,
                'stages': [
                    {'id': s.id, 'name': s.name, 'order': s.order}
                    for s in t.stages.order_by('order')
                ],
                'created_at': t.created_at.isoformat(),
            })
        return JsonResponse({'templates': result})

    def post(self, request):
        """Создать шаблон ГГ (только admin)."""
        employee = getattr(request.user, 'employee', None)
        if not employee or employee.role != 'admin':
            return JsonResponse({'error': 'Нет прав администратора'}, status=403)

        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        name = (data.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'Название обязательно'}, status=400)

        template = GGTemplate.objects.create(name=name, created_by=employee)

        # Создаём этапы шаблона
        stages_data = data.get('stages', [])
        for i, s in enumerate(stages_data):
            GGTemplateStage.objects.create(
                template=template,
                name=(s.get('name') or '').strip() or f'Этап {i + 1}',
                order=s.get('order', i + 1),
            )

        return JsonResponse({'ok': True, 'id': template.id}, status=201)


class GGTemplateDetailView(AdminRequiredJsonMixin, View):
    """DELETE /api/enterprise/gg_templates/<id>/"""

    def delete(self, request, pk):
        try:
            template = GGTemplate.objects.get(pk=pk)
        except GGTemplate.DoesNotExist:
            return JsonResponse({'error': 'Шаблон не найден'}, status=404)
        template.delete()
        return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
#  Этапы ГГ
# ---------------------------------------------------------------------------

class GGStageCreateView(WriterRequiredJsonMixin, View):
    """POST /api/enterprise/gg/<project_id>/stages/"""

    def post(self, request, project_id):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            schedule = GeneralSchedule.objects.get(project_id=project_id)
        except GeneralSchedule.DoesNotExist:
            return JsonResponse({'error': 'ГГ не найден'}, status=404)

        name = (data.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'Название обязательно'}, status=400)

        # Валидация parent_stage
        parent_id = data.get('parent_stage_id')
        if parent_id and not schedule.stages.filter(pk=parent_id).exists():
            return JsonResponse({'error': 'Родительский этап не найден'}, status=400)

        max_order = schedule.stages.order_by('-order').values_list('order', flat=True).first() or 0

        stage = GGStage.objects.create(
            schedule=schedule,
            name=name,
            date_start=data.get('date_start'),
            date_end=data.get('date_end'),
            labor=data.get('labor'),
            order=data.get('order', max_order + 1),
            parent_stage_id=parent_id,
        )
        return JsonResponse({'ok': True, 'stage': _serialize_stage(stage)}, status=201)


class GGStageDetailView(WriterRequiredJsonMixin, View):
    """PUT/DELETE /api/enterprise/gg_stages/<id>/"""

    def put(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            stage = GGStage.objects.get(pk=pk)
        except GGStage.DoesNotExist:
            return JsonResponse({'error': 'Этап не найден'}, status=404)

        FIELDS = ('name', 'date_start', 'date_end', 'labor', 'order', 'parent_stage_id')
        update_fields = []
        for f in FIELDS:
            if f in data:
                setattr(stage, f, data[f])
                update_fields.append(f)

        if update_fields:
            stage.save(update_fields=update_fields)

            # Каскад: синхронизируем связанные этапы сквозного графика
            SYNC_FIELDS = ('name', 'date_start', 'date_end')
            sync_fields = [f for f in update_fields if f in SYNC_FIELDS]
            if sync_fields:
                sync_data = {f: getattr(stage, f) for f in sync_fields}
                stage.cross_stages.update(**sync_data)

        return JsonResponse({'ok': True, 'stage': _serialize_stage(stage)})

    def delete(self, request, pk):
        try:
            stage = GGStage.objects.get(pk=pk)
        except GGStage.DoesNotExist:
            return JsonResponse({'error': 'Этап не найден'}, status=404)
        stage.delete()
        return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
#  Вехи ГГ
# ---------------------------------------------------------------------------

class GGMilestoneCreateView(WriterRequiredJsonMixin, View):
    """POST /api/enterprise/gg/<project_id>/milestones/"""

    def post(self, request, project_id):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            schedule = GeneralSchedule.objects.get(project_id=project_id)
        except GeneralSchedule.DoesNotExist:
            return JsonResponse({'error': 'ГГ не найден'}, status=404)

        name = (data.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'Название обязательно'}, status=400)

        milestone = GGMilestone.objects.create(
            schedule=schedule,
            name=name,
            date=data.get('date'),
            stage_id=data.get('stage_id'),
        )
        return JsonResponse({
            'ok': True,
            'milestone': _serialize_milestone(milestone),
        }, status=201)


class GGMilestoneDetailView(WriterRequiredJsonMixin, View):
    """PUT/DELETE /api/enterprise/gg_milestones/<id>/"""

    def put(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            ms = GGMilestone.objects.get(pk=pk)
        except GGMilestone.DoesNotExist:
            return JsonResponse({'error': 'Веха не найдена'}, status=404)

        FIELDS = ('name', 'date', 'stage_id')
        update_fields = []
        for f in FIELDS:
            if f in data:
                setattr(ms, f, data[f])
                update_fields.append(f)

        if update_fields:
            ms.save(update_fields=update_fields)
        return JsonResponse({'ok': True, 'milestone': _serialize_milestone(ms)})

    def delete(self, request, pk):
        try:
            ms = GGMilestone.objects.get(pk=pk)
        except GGMilestone.DoesNotExist:
            return JsonResponse({'error': 'Веха не найдена'}, status=404)
        ms.delete()
        return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
#  Зависимости этапов ГГ
# ---------------------------------------------------------------------------

class GGStageDependencyCreateView(WriterRequiredJsonMixin, View):
    """POST /api/enterprise/gg_stage_deps/"""

    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        pred_id = data.get('predecessor_id')
        succ_id = data.get('successor_id')
        if not pred_id or not succ_id:
            return JsonResponse(
                {'error': 'predecessor_id и successor_id обязательны'}, status=400,
            )
        if pred_id == succ_id:
            return JsonResponse({'error': 'Нельзя зависеть от самого себя'}, status=400)

        # Проверяем существование этапов и принадлежность одному ГГ
        pred = GGStage.objects.filter(pk=pred_id).values_list('schedule_id', flat=True).first()
        if pred is None:
            return JsonResponse({'error': 'Предшественник не найден'}, status=404)
        succ = GGStage.objects.filter(pk=succ_id).values_list('schedule_id', flat=True).first()
        if succ is None:
            return JsonResponse({'error': 'Последователь не найден'}, status=404)
        if pred != succ:
            return JsonResponse({'error': 'Этапы должны принадлежать одному генеральному графику'}, status=400)

        # Проверяем дублирование
        if GGStageDependency.objects.filter(
            predecessor_id=pred_id, successor_id=succ_id,
        ).exists():
            return JsonResponse({'error': 'Такая зависимость уже существует'}, status=400)

        dep = GGStageDependency.objects.create(
            predecessor_id=pred_id,
            successor_id=succ_id,
            dep_type=data.get('dep_type', 'FS'),
            lag_days=data.get('lag_days', 0),
        )
        return JsonResponse({
            'ok': True,
            'dependency': _serialize_dependency(dep),
        }, status=201)


class GGStageDependencyDetailView(WriterRequiredJsonMixin, View):
    """DELETE /api/enterprise/gg_stage_deps/<id>/"""

    def delete(self, request, pk):
        try:
            dep = GGStageDependency.objects.get(pk=pk)
        except GGStageDependency.DoesNotExist:
            return JsonResponse({'error': 'Зависимость не найдена'}, status=404)
        dep.delete()
        return JsonResponse({'ok': True})
