"""
API проектов производственного плана (PPProject).

Аналог Flask-эндпоинтов:
  GET    /api/pp_projects        — список проектов ПП
  POST   /api/pp_projects        — создание проекта ПП
  PUT    /api/pp_projects/<id>   — обновление проекта ПП
  DELETE /api/pp_projects/<id>   — удаление проекта ПП
"""
# Стандартный логгер Python
import logging

# transaction — для атомарных операций с БД (всё или ничего)
from django.db import transaction

# Count — агрегационная функция для подсчёта связанных записей
from django.db.models import Count

# JsonResponse — возврат JSON-ответа
from django.http import JsonResponse

# View — базовый класс для class-based views
from django.views import View

# Миксины авторизации и вспомогательная функция парсинга тела запроса
from apps.api.mixins import (
    AdminRequiredJsonMixin,
    LoginRequiredJsonMixin,
    parse_json_body,
)

# Модели производственного плана: проект ПП, универсальная запись работы
from apps.works.models import PPProject, Work

# Логгер для данного модуля
logger = logging.getLogger(__name__)


def _serialize_project(proj, row_count=None):
    """Сериализует PPProject в dict для JSON-ответа."""
    d = {
        'id': proj.id,                         # первичный ключ проекта ПП
        'name': proj.name or '',               # название проекта ПП
        'directory_id': proj.directory_id,     # FK на запись в справочнике (legacy)
        'up_project_id': proj.up_project_id,   # FK на УП-проект (Project)
        # Полное название связанного УП-проекта (если есть)
        'up_project_name': (proj.up_project.name_full or proj.up_project.name_short)
                           if proj.up_project else '',
        'up_product_id': proj.up_product_id,   # FK на изделие УП-проекта
        # Название изделия (если есть связь)
        'up_product_name': proj.up_product.name if proj.up_product else '',
        # Дата создания в ISO-формате (пустая строка если None)
        'created_at': proj.created_at.isoformat() if proj.created_at else '',
    }
    if row_count is not None:
        # Добавляем количество строк ПП (аннотация из ORM), если передано
        d['row_count'] = row_count
    return d


# ---------------------------------------------------------------------------
#  GET / POST  /api/pp_projects
# ---------------------------------------------------------------------------

class PPProjectListView(LoginRequiredJsonMixin, View):
    """GET — список проектов ПП; POST обрабатывается в PPProjectCreateView."""

    def get(self, request):
        try:
            # row_count = полное количество строк ПП (без фильтра по отделу),
            # так как пользователи видят весь ПП, фильтрация — только на клиенте
            projects = PPProject.objects.select_related('up_project', 'up_product').annotate(
                row_count=Count('pp_works'),
            ).order_by('-id')  # Сортировка: новые сначала

            # Сериализуем каждый проект в dict, передавая аннотированный счётчик
            result = [
                _serialize_project(p, row_count=p.row_count)
                for p in projects
            ]
            # Возвращаем JSON-список (safe=False разрешает сериализацию списков)
            resp = JsonResponse(result, safe=False)
            resp['X-Total-Count'] = len(result)
            return resp
        except Exception as e:
            # Логируем ошибку с полным трейсбеком
            logger.error("PPProjectListView.get error: %s", e, exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )


class PPProjectCreateView(AdminRequiredJsonMixin, View):
    """POST /api/pp_projects — создание проекта ПП (только admin)."""

    def post(self, request):
        try:
            # Делегируем логику создания во внутренний метод
            return self._create(request)
        except Exception as e:
            logger.error("PPProjectCreateView error: %s", e, exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def _create(self, request):
        # Парсим JSON-тело запроса
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        # Получаем и очищаем название проекта
        name = (d.get('name') or '').strip()
        if not name:
            # Название обязательно — возвращаем ошибку 400
            return JsonResponse(
                {'error': 'Название обязательно'}, status=400,
            )

        # Опциональные FK: ID из справочника, УП-проект, изделие УП-проекта
        directory_id  = d.get('directory_id') or None
        up_project_id = d.get('up_project_id') or None
        up_product_id = d.get('up_product_id') or None
        # Создаём запись PPProject в базе данных
        project = PPProject.objects.create(
            name=name,
            directory_id=directory_id,
            up_project_id=up_project_id,
            up_product_id=up_product_id,
        )
        # Возвращаем ID и основные поля созданного проекта
        return JsonResponse({'id': project.id, 'name': project.name,
                             'up_project_id': project.up_project_id,
                             'up_product_id': project.up_product_id})


# ---------------------------------------------------------------------------
#  PUT / DELETE  /api/pp_projects/<id>
# ---------------------------------------------------------------------------

class PPProjectDetailView(AdminRequiredJsonMixin, View):
    """PUT /api/pp_projects/<id>; DELETE /api/pp_projects/<id> — только admin."""

    def put(self, request, pk):
        try:
            # Делегируем обновление внутреннему методу
            return self._update(request, pk)
        except Exception as e:
            logger.error("PPProjectDetailView.put error: %s", e, exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def delete(self, request, pk):
        try:
            # Делегируем удаление внутреннему методу
            return self._delete(request, pk)
        except Exception as e:
            logger.error("PPProjectDetailView.delete error: %s", e,
                         exc_info=True)
            return JsonResponse(
                {'error': 'Внутренняя ошибка сервера'}, status=500,
            )

    def _update(self, request, pk):
        # Парсим тело запроса
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        # Проверяем наличие названия
        name = (d.get('name') or '').strip()
        if not name:
            return JsonResponse(
                {'error': 'Название обязательно'}, status=400,
            )

        # Ищем проект по первичному ключу
        try:
            project = PPProject.objects.get(pk=pk)
        except PPProject.DoesNotExist:
            return JsonResponse(
                {'error': 'Проект не найден'}, status=404,
            )

        # Обновляем название
        project.name = name
        # Обновляем FK на УП-проект (если передан — применяем, иначе сохраняем старый)
        up_project_id = d.get('up_project_id', project.up_project_id)
        project.up_project_id = up_project_id or None  # пустое значение → None
        # Обновляем FK на изделие УП-проекта
        up_product_id = d.get('up_product_id', project.up_product_id)
        project.up_product_id = up_product_id or None
        # Сохраняем только изменённые поля (оптимизация: без лишнего UPDATE)
        project.save(update_fields=['name', 'up_project_id', 'up_product_id'])
        return JsonResponse({'ok': True})

    def _delete(self, request, pk):
        # Ищем проект по PK
        try:
            project = PPProject.objects.get(pk=pk)
        except PPProject.DoesNotExist:
            return JsonResponse(
                {'error': 'Проект не найден'}, status=404,
            )

        # Удаляем в транзакции: сначала связанные Work, затем сам проект
        with transaction.atomic():
            # Удаляем все Work с show_in_pp=True, связанные с данным проектом ПП
            Work.objects.filter(pp_project=project, show_in_pp=True).delete()
            # Удаляем сам проект ПП
            project.delete()

        return JsonResponse({'ok': True})
