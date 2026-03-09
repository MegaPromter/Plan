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
# Стандартный логгер Python
import logging

# Count — агрегация: подсчёт связанных объектов
from django.db.models import Count
# JsonResponse — HTTP-ответ в формате JSON
from django.http import JsonResponse
# View — базовый класс CBV
from django.views import View

# Миксины авторизации (login, writer, admin) и парсер тела запроса
from apps.api.mixins import (
    LoginRequiredJsonMixin,
    AdminRequiredJsonMixin,
    parse_json_body,
)
# Модели: Project (УП-проект), ProjectProduct (изделие проекта),
# PPProject (план ПП, связанный с УП-проектом)
from apps.works.models import Project, ProjectProduct, PPProject

# Логгер для данного модуля
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _serialize_project(proj, extra=None):
    """Сериализует Project (УП) в dict для JSON-ответа."""
    d = {
        'id':         proj.id,                # первичный ключ УП-проекта
        'name_full':  proj.name_full or '',   # полное наименование
        'name_short': proj.name_short or '',  # краткое наименование
        'code':       proj.code or '',         # код проекта (шифр)
        # Дата создания в ISO-формате
        'created_at': proj.created_at.isoformat() if proj.created_at else '',
    }
    if extra:
        # Дополнительные поля (products, pp_count и т.д.)
        d.update(extra)
    return d


def _serialize_product(prod):
    """Сериализует ProjectProduct (изделие УП-проекта) в dict."""
    return {
        'id':      prod.id,             # первичный ключ изделия
        'name':    prod.name or '',     # наименование изделия
        'code':    prod.code or '',     # обозначение/код изделия
        'project': prod.project_id,    # FK на УП-проект (ID)
    }


# ---------------------------------------------------------------------------
#  GET /api/projects/
# ---------------------------------------------------------------------------

class ProjectListView(LoginRequiredJsonMixin, View):
    """GET — список всех УП-проектов с изделиями и количеством ПП-планов."""

    def get(self, request):
        try:
            # Получаем проекты с prefetch изделий и аннотацией количества ПП-планов
            qs = (
                Project.objects
                .prefetch_related('products', 'pp_plans')  # подгружаем связанные объекты
                .annotate(
                    # pp_count: количество связанных PPProject (производственных планов)
                    pp_count=Count('pp_plans', distinct=True),
                )
                .order_by('name_short', 'name_full')  # Сортировка: по краткому, затем полному имени
            )
            result = []
            for proj in qs:
                # Дополнительные данные для каждого проекта
                extra = {
                    # Сериализуем все изделия проекта
                    'products': [_serialize_product(p) for p in proj.products.all()],
                    # Количество связанных ПП-планов (из аннотации)
                    'pp_count': proj.pp_count,
                }
                result.append(_serialize_project(proj, extra))
            # Возвращаем JSON-список
            return JsonResponse(result, safe=False)
        except Exception as e:
            logger.error('ProjectListView.get: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  POST /api/projects/create/
# ---------------------------------------------------------------------------

class ProjectCreateView(AdminRequiredJsonMixin, View):
    """POST — создание нового УП-проекта."""

    def post(self, request):
        try:
            # Парсим JSON-тело запроса
            d = parse_json_body(request)
            # Обязательное поле: полное наименование
            name_full  = (d.get('name_full') or '').strip()
            # Необязательное: краткое наименование
            name_short = (d.get('name_short') or '').strip()
            # Необязательное: код/шифр проекта
            code       = (d.get('code') or '').strip()
            if not name_full:
                # Полное наименование обязательно
                return JsonResponse({'error': 'Полное наименование обязательно'}, status=400)
            # Создаём запись Project в БД
            proj = Project.objects.create(
                name_full=name_full,
                name_short=name_short,
                # Если код не передан — используем краткое наименование как код
                code=code or name_short,
            )
            # Возвращаем сериализованный проект с пустыми списками (новый проект)
            return JsonResponse(_serialize_project(proj, {'products': [], 'pp_count': 0}), status=201)
        except Exception as e:
            logger.error('ProjectCreateView: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/projects/<id>/
# ---------------------------------------------------------------------------

class ProjectDetailView(AdminRequiredJsonMixin, View):
    """PUT — обновление УП-проекта; DELETE — удаление."""

    def put(self, request, pk):
        try:
            # Парсим тело запроса
            d = parse_json_body(request)
            # Ищем проект по PK
            proj = Project.objects.filter(pk=pk).first()
            if not proj:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            # Получаем новые значения полей
            name_full  = (d.get('name_full') or '').strip()
            name_short = (d.get('name_short') or '').strip()
            code       = (d.get('code') or '').strip()
            if not name_full:
                # Полное наименование обязательно
                return JsonResponse({'error': 'Полное наименование обязательно'}, status=400)
            # Обновляем поля проекта
            proj.name_full  = name_full
            proj.name_short = name_short
            # Если код не передан — используем краткое наименование
            proj.code       = code or name_short
            # Сохраняем только изменённые поля
            proj.save(update_fields=['name_full', 'name_short', 'code'])
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('ProjectDetailView.put: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)

    def delete(self, request, pk):
        try:
            # Ищем проект
            proj = Project.objects.filter(pk=pk).first()
            if not proj:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            # Удаляем проект (CASCADE удалит связанные ProjectProduct и PPProject.up_project → SET NULL)
            proj.delete()
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('ProjectDetailView.delete: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  Products: GET / POST  /api/projects/<id>/products/
# ---------------------------------------------------------------------------

class ProjectProductListView(LoginRequiredJsonMixin, View):
    """GET — список изделий конкретного УП-проекта."""

    def get(self, request, pk):
        try:
            # Проверяем существование проекта
            proj = Project.objects.filter(pk=pk).first()
            if not proj:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            # Получаем изделия проекта, сортируем по названию
            products = proj.products.order_by('name')
            # Сериализуем список изделий
            return JsonResponse([_serialize_product(p) for p in products], safe=False)
        except Exception as e:
            logger.error('ProjectProductListView.get: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


class ProjectProductCreateView(AdminRequiredJsonMixin, View):
    """POST — создание нового изделия в рамках УП-проекта."""

    def post(self, request, pk):
        try:
            # Проверяем существование проекта
            proj = Project.objects.filter(pk=pk).first()
            if not proj:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            # Парсим тело запроса
            d = parse_json_body(request)
            # Наименование изделия (обязательное)
            name = (d.get('name') or '').strip()
            # Код/обозначение изделия (необязательное)
            code = (d.get('code') or '').strip()
            if not name:
                return JsonResponse({'error': 'Наименование обязательно'}, status=400)
            # Создаём изделие, привязанное к проекту
            prod = ProjectProduct.objects.create(project=proj, name=name, code=code)
            # Возвращаем сериализованное изделие с кодом 201 Created
            return JsonResponse(_serialize_product(prod), status=201)
        except Exception as e:
            logger.error('ProjectProductCreateView: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  Products: PUT / DELETE  /api/projects/<id>/products/<pid>/
# ---------------------------------------------------------------------------

class ProjectProductDetailView(AdminRequiredJsonMixin, View):
    """PUT — обновление изделия; DELETE — удаление изделия."""

    def put(self, request, pk, pid):
        try:
            # Ищем изделие по PK изделия И PK проекта (защита от подмены)
            prod = ProjectProduct.objects.filter(pk=pid, project_id=pk).first()
            if not prod:
                return JsonResponse({'error': 'Изделие не найдено'}, status=404)
            # Парсим тело запроса
            d = parse_json_body(request)
            # Новое наименование (обязательное)
            name = (d.get('name') or '').strip()
            # Новый код (необязательный)
            code = (d.get('code') or '').strip()
            if not name:
                return JsonResponse({'error': 'Наименование обязательно'}, status=400)
            # Обновляем изделие
            prod.name = name
            prod.code = code
            # Сохраняем только изменённые поля
            prod.save(update_fields=['name', 'code'])
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('ProjectProductDetailView.put: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)

    def delete(self, request, pk, pid):
        try:
            # Ищем изделие по PK изделия И PK проекта (защита от подмены)
            prod = ProjectProduct.objects.filter(pk=pid, project_id=pk).first()
            if not prod:
                return JsonResponse({'error': 'Изделие не найдено'}, status=404)
            # Удаляем изделие
            prod.delete()
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('ProjectProductDetailView.delete: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)
