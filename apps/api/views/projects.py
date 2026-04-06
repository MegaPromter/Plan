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
from datetime import date

# Count — агрегация: подсчёт связанных объектов
from django.db.models import Count

# JsonResponse — HTTP-ответ в формате JSON
from django.http import JsonResponse

# View — базовый класс CBV
from django.views import View

# Миксины авторизации (login, writer, admin) и парсер тела запроса
from apps.api.mixins import (
    AdminRequiredJsonMixin,
    LoginRequiredJsonMixin,
    parse_json_body,
)

# Модели: Project (УП-проект), ProjectProduct (изделие проекта),
# PPProject (план ПП, связанный с УП-проектом), Work (задача)
from apps.works.models import PPProject, Project, ProjectProduct, Work

# Логгер для данного модуля
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _sync_pp_names_on_product_change(product, old_name, old_code):
    """Обновляет PPProject.name при переименовании изделия.

    Заменяет старое название/код изделия на новое в названии связанных ПП.
    """
    pp_plans = PPProject.objects.filter(up_product=product)
    for pp in pp_plans:
        new_pp_name = pp.name
        # Заменяем старое название изделия на новое
        if old_name and old_name in new_pp_name:
            new_pp_name = new_pp_name.replace(old_name, product.name)
        # Заменяем старый код изделия на новый
        if old_code and old_code in new_pp_name:
            new_pp_name = new_pp_name.replace(old_code, product.code or '')
        if new_pp_name != pp.name:
            pp.name = new_pp_name.strip()
            pp.save(update_fields=['name'])


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
        'id':         prod.id,                 # первичный ключ изделия
        'name':       prod.name or '',         # наименование изделия
        'name_short': prod.name_short or '',   # краткое наименование
        'code':       prod.code or '',         # обозначение/код изделия
        'project':    prod.project_id,         # FK на УП-проект (ID)
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
                    # stages_count: количество этапов (PPStage)
                    stages_count=Count('stages', distinct=True),
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
                    # Количество этапов проекта
                    'stages_count': proj.stages_count,
                }
                result.append(_serialize_project(proj, extra))
            # Возвращаем JSON-список
            response = JsonResponse(result, safe=False)
            response['Cache-Control'] = 'private, max-age=30'
            return response
        except Exception as e:
            logger.error('ProjectListView.get: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)


# ---------------------------------------------------------------------------
#  GET /api/projects/<id>/metrics/
# ---------------------------------------------------------------------------

class ProjectMetricsView(LoginRequiredJsonMixin, View):
    """GET — метрики проекта: задачи, исполнители, сроки, загрузка."""

    def get(self, request, project_id):
        try:
            proj = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return JsonResponse({'error': 'Проект не найден'}, status=404)

        today = date.today()

        # ПП-планы проекта
        pp_projects = PPProject.objects.filter(up_project=proj)
        pp_ids = list(pp_projects.values_list('id', flat=True))

        # Все задачи проекта: через прямую связь ИЛИ через ПП
        from django.db.models import Exists, OuterRef, Q

        from apps.works.models import WorkReport
        works = Work.objects.filter(
            Q(project=proj) | Q(pp_project_id__in=pp_ids)
        ).select_related(
            'executor', 'pp_project'
        ).prefetch_related(
            'task_executors'
        ).annotate(
            has_reports=Exists(WorkReport.objects.filter(work=OuterRef('pk')))
        ).distinct()

        total = works.count()
        done = 0
        in_work = 0
        overdue = 0
        total_hours = 0.0
        executors_set = set()
        date_min = None
        date_max = None
        pp_set = set()

        for w in works:
            is_done = w.has_reports

            if is_done:
                done += 1
            elif w.date_end and w.date_end < today:
                overdue += 1
                in_work += 1
            else:
                in_work += 1

            # Часы
            if hasattr(w, 'plan_hours') and w.plan_hours:
                total_hours += sum(float(v) for v in w.plan_hours.values())
            for te in w.task_executors.all():
                if te.plan_hours:
                    total_hours += sum(float(v) for v in te.plan_hours.values())
                if te.executor_id:
                    executors_set.add((te.executor_id, te.executor_name))

            # Исполнитель основной
            if w.executor_id:
                name = ''
                if w.executor:
                    name = w.executor.short_name or str(w.executor)
                executors_set.add((w.executor_id, name))

            # Сроки
            if w.date_start:
                if date_min is None or w.date_start < date_min:
                    date_min = w.date_start
            if w.date_end:
                if date_max is None or w.date_end > date_max:
                    date_max = w.date_end

            # ПП
            if w.pp_project_id:
                pp_set.add((w.pp_project_id, str(w.pp_project) if w.pp_project else ''))

        # Изделия
        products = list(proj.products.values('id', 'name', 'code'))

        # ПП планы — из задач + из прямой связи
        for pp in pp_projects:
            pp_set.add((pp.id, pp.name or str(pp)))
        pp_plans = []
        for pp_id, pp_name in sorted(pp_set, key=lambda x: x[1]):
            pp_plans.append({'id': pp_id, 'name': pp_name})

        # Исполнители
        executors = []
        for eid, ename in sorted(executors_set, key=lambda x: x[1]):
            executors.append({'id': eid, 'name': ename})

        return JsonResponse({
            'id': proj.id,
            'name_full': proj.name_full or '',
            'name_short': proj.name_short or '',
            'code': proj.code or '',
            'tasks': {
                'total': total,
                'done': done,
                'in_work': in_work,
                'overdue': overdue,
            },
            'total_hours': round(total_hours, 1),
            'date_start': date_min.isoformat() if date_min else None,
            'date_end': date_max.isoformat() if date_max else None,
            'products': products,
            'pp_plans': pp_plans,
            'executors': executors,
        })


# ---------------------------------------------------------------------------
#  POST /api/projects/create/
# ---------------------------------------------------------------------------

class ProjectCreateView(AdminRequiredJsonMixin, View):
    """POST — создание нового УП-проекта."""

    def post(self, request):
        try:
            # Парсим JSON-тело запроса
            d = parse_json_body(request)
            if d is None:
                return JsonResponse({'error': 'Невалидный JSON'}, status=400)
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
            if d is None:
                return JsonResponse({'error': 'Невалидный JSON'}, status=400)
            # Ищем проект по PK
            try:
                proj = Project.objects.get(pk=pk)
            except Project.DoesNotExist:
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
            try:
                proj = Project.objects.get(pk=pk)
            except Project.DoesNotExist:
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
            try:
                proj = Project.objects.get(pk=pk)
            except Project.DoesNotExist:
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
            try:
                proj = Project.objects.get(pk=pk)
            except Project.DoesNotExist:
                return JsonResponse({'error': 'Проект не найден'}, status=404)
            # Парсим тело запроса
            d = parse_json_body(request)
            if d is None:
                return JsonResponse({'error': 'Невалидный JSON'}, status=400)
            # Наименование изделия (обязательное)
            name = (d.get('name') or '').strip()
            # Краткое наименование изделия (необязательное)
            name_short = (d.get('name_short') or '').strip()
            # Код/обозначение изделия (необязательное)
            code = (d.get('code') or '').strip()
            if not name:
                return JsonResponse({'error': 'Наименование обязательно'}, status=400)
            # Создаём изделие, привязанное к проекту
            prod = ProjectProduct.objects.create(
                project=proj, name=name, name_short=name_short, code=code,
            )
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
            try:
                prod = ProjectProduct.objects.get(pk=pid, project_id=pk)
            except ProjectProduct.DoesNotExist:
                return JsonResponse({'error': 'Изделие не найдено'}, status=404)
            # Парсим тело запроса
            d = parse_json_body(request)
            if d is None:
                return JsonResponse({'error': 'Невалидный JSON'}, status=400)
            # Новое наименование (обязательное)
            name = (d.get('name') or '').strip()
            # Новое краткое наименование (необязательное)
            name_short = (d.get('name_short') or '').strip()
            # Новый код (необязательный)
            code = (d.get('code') or '').strip()
            if not name:
                return JsonResponse({'error': 'Наименование обязательно'}, status=400)
            # Запоминаем старое название для синхронизации ПП
            old_name = prod.name
            old_code = prod.code
            # Обновляем поля изделия
            prod.name = name
            prod.name_short = name_short  # краткое наименование
            prod.code = code
            # Сохраняем только изменённые поля
            prod.save(update_fields=['name', 'name_short', 'code'])
            # Синхронизируем название связанных ПП (PPProject)
            if old_name != name or old_code != code:
                _sync_pp_names_on_product_change(prod, old_name, old_code)
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('ProjectProductDetailView.put: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)

    def delete(self, request, pk, pid):
        try:
            # Ищем изделие по PK изделия И PK проекта (защита от подмены)
            try:
                prod = ProjectProduct.objects.get(pk=pid, project_id=pk)
            except ProjectProduct.DoesNotExist:
                return JsonResponse({'error': 'Изделие не найдено'}, status=404)
            # Удаляем изделие
            prod.delete()
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('ProjectProductDetailView.delete: %s', e, exc_info=True)
            return JsonResponse({'error': 'Ошибка сервера'}, status=500)
