"""
API для справочников (directories).

CRUD-операции над универсальной таблицей Directory.
GET     /api/directories          -- список справочников (+ виртуальные employees)
POST    /api/directories          -- создание записи (admin)
PUT     /api/directories/<id>     -- обновление записи (admin)
DELETE  /api/directories/<id>     -- удаление записи (admin)
"""
# Стандартный логгер Python
import logging

# defaultdict — словарь с дефолтным значением (используется для группировки)
from collections import defaultdict, deque

# cache — серверный кэш Django (memcache/redis/locmem в зависимости от настроек)
from django.core.cache import cache

# JsonResponse — HTTP-ответ с JSON-телом
from django.http import JsonResponse

# View — базовый класс для CBV
from django.views import View

# Миксины авторизации: admin и login, а также парсер JSON-тела
from apps.api.mixins import (
    AdminRequiredJsonMixin,
    LoginRequiredJsonMixin,
    parse_json_body,
)
from apps.api.utils import short_name

# Модели сотрудников: Employee (профиль), Department (отдел),
# Sector (сектор), NTCCenter (НТЦ-центр)
from apps.employees.models import Department, Employee, NTCCenter, Sector

# Модели работ: Directory (справочник), PPProject (проект ПП)
from apps.works.models import Directory, PPProject, Project, Work

# Логгер для данного модуля
logger = logging.getLogger(__name__)

# Ключ и TTL серверного кэша справочников (5 минут)
DIRECTORIES_CACHE_KEY = 'directories_list'
DIRECTORIES_CACHE_TTL = 300


# ── GET /api/directories ─────────────────────────────────────────────────────

class DirectoryListView(LoginRequiredJsonMixin, View):
    """
    GET  -- возвращает все записи справочника, сгруппированные по типу.
           Дополнительно формирует виртуальный справочник employees
           (ФИО + подразделение) для выпадающих списков.
    """

    # Типы, которые заменены реальными моделями — не читаем из Directory
    # Для этих типов используются модели NTCCenter, Department, Sector
    _REAL_MODEL_TYPES = {'center', 'dept', 'sector', 'task_type'}

    def get(self, request):
        # Проверяем серверный кэш (справочники меняются редко)
        cached = cache.get(DIRECTORIES_CACHE_KEY)
        if cached is not None:
            response = JsonResponse(cached)
            response['Cache-Control'] = 'max-age=60'
            return response

        # Исключаем типы, дублирующие реальные модели (NTCCenter, Department, Sector)
        # Они обрабатываются отдельно ниже
        qs = Directory.objects.exclude(
            dir_type__in=self._REAL_MODEL_TYPES,
        ).order_by('dir_type', 'value')

        # Группируем записи справочника по типу (dir_type → список записей)
        result = defaultdict(list)
        for d in qs:
            result[d.dir_type].append({
                'id': d.pk,           # первичный ключ записи справочника
                'value': d.value,     # значение (название/код)
                'parent_id': d.parent_id,  # FK на родительскую запись (для иерархий)
            })

        # Виртуальные записи из реальных моделей (заменяют Directory типов center/dept/sector)
        # НТЦ-центры из модели NTCCenter
        result['center'] = [
            {'id': c.pk, 'value': c.code, 'parent_id': None}
            for c in NTCCenter.objects.order_by('code')
        ]
        # Отделы из модели Department
        result['dept'] = [
            {'id': d.pk, 'value': d.code, 'parent_id': None}
            for d in Department.objects.order_by('code')
        ]
        # short_name() — в apps/api/utils.py

        # Начальники секторов — нужны для подстановки в таблицу ПП (колонка «Нач. сектора»)
        sector_heads = {}
        for emp in Employee.objects.filter(role=Employee.ROLE_SECTOR_HEAD).select_related('sector'):
            if emp.sector:
                sector_heads[emp.sector.code] = short_name(emp.full_name)

        result['sector'] = [
            {
                'id': s.pk,
                'value': s.code,
                'parent_id': s.department_id,
                'head_name': sector_heads.get(s.code, ''),  # ФИО начальника сектора
            }
            for s in Sector.objects.select_related('department').order_by('department__code', 'code')
        ]

        # Виртуальный справочник сотрудников (для автодополнения поля «Исполнитель»)
        emp_qs = (
            Employee.objects
            .exclude(last_name='')          # исключаем сотрудников без фамилии
            .select_related('department', 'sector')
            .order_by('last_name', 'first_name')
        )
        employees = []
        for emp in emp_qs:
            # Полное имя (Фамилия Имя Отчество)
            full = emp.full_name
            # Код отдела (пустая строка если нет отдела)
            dept_code = emp.department.code if emp.department else ''
            # Код сектора (пустая строка если нет сектора)
            sector_code = emp.sector.code if emp.sector else ''
            # Читаемое название должности (через choices)
            position = emp.get_position_display() if emp.position else ''

            # Добавляем сокращённое имя (Фамилия И.О.),
            # если сокращение недоступно — используем полное имя
            abbrev = emp.short_name
            employees.append({
                'id': emp.pk,
                'value': abbrev if abbrev else full,
                'dept': dept_code,
                'sector': sector_code,
                'position': position,
            })

        # Виртуальный справочник проектов (из модели Project)
        result['project'] = [
            {'id': p.pk, 'value': p.name, 'parent_id': None}
            for p in Project.objects.order_by('name_short', 'name_full')
        ]

        # Виртуальный справочник этапов (уникальные stage_num из Work)
        stage_vals = sorted(set(
            Work.objects.exclude(stage_num='')
            .values_list('stage_num', flat=True)
        ))
        result['stage'] = [
            {'id': idx, 'value': v, 'parent_id': None}
            for idx, v in enumerate(stage_vals, start=1)
        ]

        # Виртуальный справочник типов задач (не зависит от seed-данных в Directory)
        _TASK_TYPES = [
            'Выпуск нового документа',
            'Корректировка документа',
            'Разработка',
            'Сопровождение (ОКАН)',
        ]
        result['task_type'] = [
            {'id': idx, 'value': v, 'parent_id': None}
            for idx, v in enumerate(_TASK_TYPES, start=1)
        ]

        # Добавляем виртуальный справочник сотрудников
        result['employees'] = employees

        # Сохраняем в серверный кэш (5 минут)
        payload = dict(result)
        cache.set(DIRECTORIES_CACHE_KEY, payload, DIRECTORIES_CACHE_TTL)

        # Формируем ответ
        response = JsonResponse(payload)
        # Браузерный кэш на 60 секунд (дополнительно к серверному)
        response['Cache-Control'] = 'max-age=60'
        return response


# ── POST / PUT / DELETE /api/directories ─────────────────────────────────────

class DirectoryCreateView(AdminRequiredJsonMixin, View):
    """POST -- создание записи справочника. Только admin."""

    def post(self, request):
        # Парсим JSON-тело
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        # Тип справочника (например: 'project', 'task_type', 'position' и т.д.)
        dir_type = data.get('type', '').strip()
        # Значение записи (код или название)
        value = data.get('value', '').strip()
        # Опциональный родитель для иерархических справочников
        parent_id = data.get('parent_id')

        if not dir_type or not value:
            # Оба поля обязательны для создания
            return JsonResponse(
                {'error': 'Поля type и value обязательны'}, status=400
            )

        # Типы center/dept/sector управляются через реальные модели, а не Directory
        if dir_type in DirectoryListView._REAL_MODEL_TYPES:
            return JsonResponse(
                {'error': f'Тип "{dir_type}" управляется через модули подразделений'},
                status=400,
            )

        # Находим родительскую запись (если указана)
        parent = None
        if parent_id:
            try:
                parent = Directory.objects.get(pk=parent_id)
            except Directory.DoesNotExist:
                return JsonResponse(
                    {'error': 'Родительская запись не найдена'}, status=404
                )

        # Создаём запись справочника
        entry = Directory.objects.create(
            dir_type=dir_type,  # тип справочника
            value=value,        # значение
            parent=parent,      # FK на родителя (None для корневых записей)
        )

        # Инвалидируем кэш справочников после создания записи
        cache.delete(DIRECTORIES_CACHE_KEY)

        # Результат: минимально — ID созданной записи
        result = {'id': entry.pk}

        # Автоматически создаём производственный проект при создании проекта
        # верхнего уровня (без parent)
        if dir_type == 'project' and not parent_id:
            # Корневой проект → создаём связанный PPProject
            pp = PPProject.objects.create(name=value, directory=entry)
            result['pp_project_id'] = pp.pk

        # Возвращаем ID с кодом 201 Created
        return JsonResponse(result, status=201)


class DirectoryDetailView(AdminRequiredJsonMixin, View):
    """
    PUT    -- обновление записи справочника.
    DELETE -- удаление записи с каскадным удалением потомков.
    """

    def put(self, request, pk):
        # Парсим тело запроса
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        # Новое значение записи (обязательное)
        value = data.get('value', '').strip()

        if not value:
            return JsonResponse(
                {'error': 'Поле value обязательно'}, status=400
            )

        # Ищем запись по PK
        try:
            entry = Directory.objects.get(pk=pk)
        except Directory.DoesNotExist:
            return JsonResponse(
                {'error': 'Запись не найдена'}, status=404
            )

        # Обновляем значение
        entry.value = value
        # Сохраняем только поле value
        entry.save(update_fields=['value'])

        # Инвалидируем кэш справочников после обновления
        cache.delete(DIRECTORIES_CACHE_KEY)

        # Синхронизируем имя в PPProject, если это проект верхнего уровня
        if entry.dir_type == 'project' and not entry.parent_id:
            # Обновляем название связанного PPProject (если он есть)
            PPProject.objects.filter(directory=entry).update(name=value)

        return JsonResponse({'ok': True})

    def delete(self, request, pk):
        # Ищем запись по PK
        try:
            entry = Directory.objects.get(pk=pk)
        except Directory.DoesNotExist:
            return JsonResponse(
                {'error': 'Запись не найдена'}, status=404
            )

        # Запоминаем, является ли это корневым проектом (для каскадного удаления ПП)
        is_top_project = (
            entry.dir_type == 'project' and not entry.parent_id
        )

        # Рекурсивный сбор всех потомков (BFS — обход в ширину)
        to_delete_ids = [entry.pk]  # начинаем с самой записи
        bfs_queue = deque([entry.pk])  # очередь для BFS
        while bfs_queue:
            pid = bfs_queue.popleft()  # берём первый элемент очереди
            # Получаем ID всех дочерних записей данного родителя
            children_ids = list(
                Directory.objects
                .filter(parent_id=pid)
                .values_list('id', flat=True)
            )
            # Добавляем дочерние ID в список на удаление
            to_delete_ids.extend(children_ids)
            # И в очередь для поиска их дочерних записей
            bfs_queue.extend(children_ids)

        # Каскадное удаление производственного плана при удалении проекта
        # (выполняем ДО удаления Directory, иначе FK directory_id уже NULL)
        if is_top_project:
            from django.db import transaction
            pp_projects = list(PPProject.objects.filter(directory_id=pk))
            if pp_projects:
                with transaction.atomic():
                    Work.objects.filter(pp_project__in=pp_projects).delete()
                    PPProject.objects.filter(pk__in=[pp.pk for pp in pp_projects]).delete()

        # Удаляем все найденные записи справочника одним запросом
        Directory.objects.filter(pk__in=to_delete_ids).delete()

        # Инвалидируем кэш справочников после удаления
        cache.delete(DIRECTORIES_CACHE_KEY)

        return JsonResponse({'ok': True})
