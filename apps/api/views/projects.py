"""
API модуля «Управление проектами» (УП).

GET    /api/projects/              — список проектов УП
POST   /api/projects/create/       — создание проекта
PUT    /api/projects/<id>/         — обновление проекта
DELETE /api/projects/<id>/         — удаление проекта

GET    /api/projects/<id>/products/        — изделия проекта
POST   /api/projects/<id>/products/create/ — создание изделия
PUT    /api/projects/<id>/products/<pid>/  — обновление изделия
DELETE /api/projects/<id>/products/<pid>/  — удаление изделия
"""
import logging

from django.db.models import Count, Sum
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.works.models import Project, ProjectProduct, PPProject, PPWork

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _serialize_project(proj, extra=None):
    d = {
        'id':         proj.id,
        'name_full':  proj.name_full or '',
        'name_short': proj.name_short or '',
        'code':       proj.code or '',
        'created_at': proj.created_at.isoformat() if proj.created_at else '',
    }
    if extra:
        d.update(extra)
    return d


def _serialize_product(prod):
    return {
        'id':      prod.id,
        'name':    prod.name or '',
        'code':    prod.code or '',
        'project': prod.project_id,
    }


# ---------------------------------------------------------------------------
#  GET /api/projects/
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class ProjectListView(LoginRequiredJsonMixin, View):

    def get(self, request):
        try:
            qs = (
                Project.objects
                .prefetch_related('products', 'pp_plans')
                .annotate(
                    pp_count=Count('pp_plans', distinct=True),
                )
                .order_by('name_short', 'name_full')
            )
            result = []
            for proj in qs:
                extra = {
                    'products': [_serialize_product(p) for p in proj.products.all()],
                    'pp_count': proj.pp_count,
                }
                result.append(_serialize_project(proj, extra))
            return JsonResponse(result, safe=False)
        except Exception as e:
            logger.error('ProjectListView.get: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  POST /api/projects/create/
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class ProjectCreateView(WriterRequiredJsonMixin, View):

    def post(self, request):
        try:
            d = parse_json_body(request)
            name_full  = (d.get('name_full') or '').strip()
            name_short = (d.get('name_short') or '').strip()
            code       = (d.get('code') or '').strip()
            if not name_full:
                return JsonResponse({'error': 'Полное наименование обязательно'}, status=400)
            proj = Project.objects.create(
                name_full=name_full,
                name_short=name_short,
                code=code or name_short,
            )
            return JsonResponse(_serialize_project(proj, {'products': [], 'pp_count': 0}), status=201)
        except Exception as e:
            logger.error('ProjectCreateView: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/projects/<id>/
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class ProjectDetailView(WriterRequiredJsonMixin, View):

    def put(self, request, pk):
        try:
            d = parse_json_body(request)
            proj = Project.objects.filter(pk=pk).first()
            if not proj:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            name_full  = (d.get('name_full') or '').strip()
            name_short = (d.get('name_short') or '').strip()
            code       = (d.get('code') or '').strip()
            if not name_full:
                return JsonResponse({'error': 'Полное наименование обязательно'}, status=400)
            proj.name_full  = name_full
            proj.name_short = name_short
            proj.code       = code or name_short
            proj.save(update_fields=['name_full', 'name_short', 'code'])
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('ProjectDetailView.put: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)

    def delete(self, request, pk):
        try:
            proj = Project.objects.filter(pk=pk).first()
            if not proj:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            proj.delete()
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('ProjectDetailView.delete: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  Products: GET / POST  /api/projects/<id>/products/
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class ProjectProductListView(LoginRequiredJsonMixin, View):

    def get(self, request, pk):
        try:
            proj = Project.objects.filter(pk=pk).first()
            if not proj:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            products = proj.products.order_by('name')
            return JsonResponse([_serialize_product(p) for p in products], safe=False)
        except Exception as e:
            logger.error('ProjectProductListView.get: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class ProjectProductCreateView(WriterRequiredJsonMixin, View):

    def post(self, request, pk):
        try:
            proj = Project.objects.filter(pk=pk).first()
            if not proj:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            d = parse_json_body(request)
            name = (d.get('name') or '').strip()
            code = (d.get('code') or '').strip()
            if not name:
                return JsonResponse({'error': 'Наименование обязательно'}, status=400)
            prod = ProjectProduct.objects.create(project=proj, name=name, code=code)
            return JsonResponse(_serialize_product(prod), status=201)
        except Exception as e:
            logger.error('ProjectProductCreateView: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  Products: PUT / DELETE  /api/projects/<id>/products/<pid>/
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class ProjectProductDetailView(WriterRequiredJsonMixin, View):

    def put(self, request, pk, pid):
        try:
            prod = ProjectProduct.objects.filter(pk=pid, project_id=pk).first()
            if not prod:
                return JsonResponse({'error': 'Изделие не найдено'}, status=404)
            d = parse_json_body(request)
            name = (d.get('name') or '').strip()
            code = (d.get('code') or '').strip()
            if not name:
                return JsonResponse({'error': 'Наименование обязательно'}, status=400)
            prod.name = name
            prod.code = code
            prod.save(update_fields=['name', 'code'])
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('ProjectProductDetailView.put: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)

    def delete(self, request, pk, pid):
        try:
            prod = ProjectProduct.objects.filter(pk=pid, project_id=pk).first()
            if not prod:
                return JsonResponse({'error': 'Изделие не найдено'}, status=404)
            prod.delete()
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('ProjectProductDetailView.delete: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)
