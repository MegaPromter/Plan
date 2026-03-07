"""
API проектов производственного плана (PPProject).

Аналог Flask-эндпоинтов:
  GET    /api/pp_projects        — список проектов ПП
  POST   /api/pp_projects        — создание проекта ПП
  PUT    /api/pp_projects/<id>   — обновление проекта ПП
  DELETE /api/pp_projects/<id>   — удаление проекта ПП
"""
import logging

from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.works.models import PPProject, PPWork, Work

logger = logging.getLogger(__name__)


def _serialize_project(proj, row_count=None):
    """Сериализует PPProject в dict для JSON-ответа."""
    d = {
        'id': proj.id,
        'name': proj.name or '',
        'directory_id': proj.directory_id,
        'up_project_id': proj.up_project_id,
        'up_project_name': (proj.up_project.name_short or proj.up_project.name_full)
                           if proj.up_project else '',
        'up_product_id': proj.up_product_id,
        'up_product_name': proj.up_product.name if proj.up_product else '',
        'created_at': proj.created_at.isoformat() if proj.created_at else '',
    }
    if row_count is not None:
        d['row_count'] = row_count
    return d


# ---------------------------------------------------------------------------
#  GET / POST  /api/pp_projects
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class PPProjectListView(LoginRequiredJsonMixin, View):
    """GET — список проектов ПП; POST обрабатывается в PPProjectCreateView."""

    def get(self, request):
        try:
            projects = PPProject.objects.select_related('up_project', 'up_product').annotate(
                row_count=Count('pp_works'),
            ).order_by('-id')

            result = [
                _serialize_project(p, row_count=p.row_count)
                for p in projects
            ]
            return JsonResponse(result, safe=False)
        except Exception as e:
            logger.error("PPProjectListView.get error: %s", e, exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )


@method_decorator(csrf_exempt, name='dispatch')
class PPProjectCreateView(WriterRequiredJsonMixin, View):
    """POST /api/pp_projects — создание проекта ПП."""

    def post(self, request):
        try:
            return self._create(request)
        except Exception as e:
            logger.error("PPProjectCreateView error: %s", e, exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def _create(self, request):
        d = parse_json_body(request)
        name = (d.get('name') or '').strip()
        if not name:
            return JsonResponse(
                {'error': 'Название обязательно'}, status=400,
            )

        directory_id  = d.get('directory_id') or None
        up_project_id = d.get('up_project_id') or None
        up_product_id = d.get('up_product_id') or None
        project = PPProject.objects.create(
            name=name,
            directory_id=directory_id,
            up_project_id=up_project_id,
            up_product_id=up_product_id,
        )
        return JsonResponse({'id': project.id, 'name': project.name,
                             'up_project_id': project.up_project_id,
                             'up_product_id': project.up_product_id})


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/pp_projects/<id>
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class PPProjectDetailView(WriterRequiredJsonMixin, View):
    """PUT /api/pp_projects/<id>; DELETE /api/pp_projects/<id>."""

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except Exception as e:
            logger.error("PPProjectDetailView.put error: %s", e, exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def delete(self, request, pk):
        try:
            return self._delete(request, pk)
        except Exception as e:
            logger.error("PPProjectDetailView.delete error: %s", e,
                         exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def _update(self, request, pk):
        d = parse_json_body(request)
        name = (d.get('name') or '').strip()
        if not name:
            return JsonResponse(
                {'error': 'Название обязательно'}, status=400,
            )

        project = PPProject.objects.filter(pk=pk).first()
        if not project:
            return JsonResponse(
                {'error': 'Проект не найден'}, status=404,
            )

        project.name = name
        up_project_id = d.get('up_project_id', project.up_project_id)
        project.up_project_id = up_project_id or None
        up_product_id = d.get('up_product_id', project.up_product_id)
        project.up_product_id = up_product_id or None
        project.save(update_fields=['name', 'up_project_id', 'up_product_id'])
        return JsonResponse({'ok': True})

    def _delete(self, request, pk):
        project = PPProject.objects.filter(pk=pk).first()
        if not project:
            return JsonResponse(
                {'error': 'Проект не найден'}, status=404,
            )

        with transaction.atomic():
            # Удаляем связанные Work (source_type='pp') через PPWork
            pp_work_ids = PPWork.objects.filter(
                pp_project=project,
            ).values_list('work_id', flat=True)
            Work.objects.filter(pk__in=pp_work_ids).delete()
            # Удаляем проект
            project.delete()

        return JsonResponse({'ok': True})
