"""
API этапов проекта (PPStage).

GET    /api/projects/<pk>/stages/              — список этапов проекта
POST   /api/projects/<pk>/stages/create/       — создание этапа
PUT    /api/projects/<pk>/stages/<stage_id>/   — обновление этапа
DELETE /api/projects/<pk>/stages/<stage_id>/   — удаление этапа
"""
import logging

from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.works.models import PPStage, Project

logger = logging.getLogger(__name__)


def _serialize_stage(s):
    return {
        'id': s.id,
        'name': s.name,
        'stage_number': s.stage_number,
        'work_order': s.work_order,
        'row_code': s.row_code,
        'order': s.order,
    }


class PPStageListView(LoginRequiredJsonMixin, View):
    """GET — список этапов проекта УП."""

    def get(self, request, pk):
        try:
            try:
                proj = Project.objects.get(pk=pk)
            except Project.DoesNotExist:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            stages = proj.stages.order_by('order', 'id')
            return JsonResponse([_serialize_stage(s) for s in stages], safe=False)
        except Exception as e:
            logger.error('PPStageListView.get: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


class PPStageCreateView(WriterRequiredJsonMixin, View):
    """POST — создание этапа."""

    def post(self, request, pk):
        try:
            try:
                proj = Project.objects.get(pk=pk)
            except Project.DoesNotExist:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            d = parse_json_body(request)
            if d is None:
                return JsonResponse({'error': 'Невалидный JSON'}, status=400)
            name = (d.get('name') or '').strip()
            if not name:
                return JsonResponse({'error': 'Наименование обязательно'}, status=400)
            stage = PPStage.objects.create(
                project=proj,
                name=name,
                stage_number=(d.get('stage_number') or '').strip(),
                work_order=(d.get('work_order') or '').strip(),
                row_code=(d.get('row_code') or '').strip(),
                order=d.get('order', 0) or 0,
            )
            return JsonResponse(_serialize_stage(stage), status=201)
        except Exception as e:
            logger.error('PPStageCreateView.post: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


class PPStageDetailView(WriterRequiredJsonMixin, View):
    """PUT — обновление; DELETE — удаление этапа."""

    def put(self, request, pk, stage_id):
        try:
            try:
                stage = PPStage.objects.get(pk=stage_id, project_id=pk)
            except PPStage.DoesNotExist:
                return JsonResponse({'error': 'Этап не найден'}, status=404)
            d = parse_json_body(request)
            if d is None:
                return JsonResponse({'error': 'Невалидный JSON'}, status=400)
            name = (d.get('name') or '').strip()
            if not name:
                return JsonResponse({'error': 'Наименование обязательно'}, status=400)
            stage.name = name
            stage.stage_number = (d.get('stage_number') or '').strip()
            stage.work_order = (d.get('work_order') or '').strip()
            stage.row_code = (d.get('row_code') or '').strip()
            if 'order' in d:
                stage.order = d['order'] or 0
            stage.save()
            return JsonResponse(_serialize_stage(stage))
        except Exception as e:
            logger.error('PPStageDetailView.put: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)

    def delete(self, request, pk, stage_id):
        try:
            try:
                stage = PPStage.objects.get(pk=stage_id, project_id=pk)
            except PPStage.DoesNotExist:
                return JsonResponse({'error': 'Этап не найден'}, status=404)
            stage.works.update(pp_stage=None)
            stage.delete()
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('PPStageDetailView.delete: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)
