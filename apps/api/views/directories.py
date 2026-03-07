"""
API для справочников (directories).

CRUD-операции над универсальной таблицей Directory.
GET     /api/directories          -- список справочников (+ виртуальные employees)
POST    /api/directories          -- создание записи (admin)
PUT     /api/directories/<id>     -- обновление записи (admin)
DELETE  /api/directories/<id>     -- удаление записи (admin)
"""
import logging
from collections import defaultdict

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.api.mixins import (
    AdminRequiredJsonMixin,
    LoginRequiredJsonMixin,
    parse_json_body,
)
from apps.employees.models import Employee, Department, Sector, NTCCenter
from apps.works.models import Directory, PPProject

logger = logging.getLogger(__name__)


# ── GET /api/directories ─────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class DirectoryListView(LoginRequiredJsonMixin, View):
    """
    GET  -- возвращает все записи справочника, сгруппированные по типу.
           Дополнительно формирует виртуальный справочник employees
           (ФИО + подразделение) для выпадающих списков.
    """

    # Типы, которые заменены реальными моделями — не читаем из Directory
    _REAL_MODEL_TYPES = {'center', 'dept', 'sector'}

    def get(self, request):
        # Исключаем типы, дублирующие реальные модели (NTCCenter, Department, Sector)
        qs = Directory.objects.exclude(
            dir_type__in=self._REAL_MODEL_TYPES,
        ).order_by('dir_type', 'value')

        # Группируем по типу
        result = defaultdict(list)
        for d in qs:
            result[d.dir_type].append({
                'id': d.pk,
                'value': d.value,
                'parent_id': d.parent_id,
            })

        # Виртуальные записи из реальных моделей
        result['center'] = [
            {'id': c.pk, 'value': c.code, 'parent_id': None}
            for c in NTCCenter.objects.order_by('code')
        ]
        result['dept'] = [
            {'id': d.pk, 'value': d.code, 'parent_id': None}
            for d in Department.objects.order_by('code')
        ]
        result['sector'] = [
            {'id': s.pk, 'value': s.code, 'parent_id': s.department_id}
            for s in Sector.objects.select_related('department').order_by('department__code', 'code')
        ]

        # Виртуальный справочник сотрудников
        emp_qs = (
            Employee.objects
            .exclude(last_name='')
            .select_related('department', 'sector')
            .order_by('last_name', 'first_name')
        )
        employees = []
        for emp in emp_qs:
            full = emp.full_name
            dept_code = emp.department.code if emp.department else ''
            position = emp.get_position_display() if emp.position else ''

            employees.append({
                'value': full,
                'dept': dept_code,
                'position': position,
            })
            # Добавляем сокращённое имя (Фамилия И.О.)
            abbrev = emp.short_name
            if abbrev and abbrev != full:
                employees.append({
                    'value': abbrev,
                    'dept': dept_code,
                    'position': position,
                })

        result['employees'] = employees

        response = JsonResponse(dict(result))
        response['Cache-Control'] = 'max-age=60'
        return response


# ── POST / PUT / DELETE /api/directories ─────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class DirectoryCreateView(AdminRequiredJsonMixin, View):
    """POST -- создание записи справочника. Только admin."""

    def post(self, request):
        data = parse_json_body(request)

        dir_type = data.get('type', '').strip()
        value = data.get('value', '').strip()
        parent_id = data.get('parent_id')

        if not dir_type or not value:
            return JsonResponse(
                {'error': 'Поля type и value обязательны'}, status=400
            )

        # Типы center/dept/sector управляются через реальные модели, а не Directory
        if dir_type in DirectoryListView._REAL_MODEL_TYPES:
            return JsonResponse(
                {'error': f'Тип "{dir_type}" управляется через модули подразделений'},
                status=400,
            )

        parent = None
        if parent_id:
            try:
                parent = Directory.objects.get(pk=parent_id)
            except Directory.DoesNotExist:
                return JsonResponse(
                    {'error': 'Родительская запись не найдена'}, status=404
                )

        entry = Directory.objects.create(
            dir_type=dir_type,
            value=value,
            parent=parent,
        )

        result = {'id': entry.pk}

        # Автоматически создаём производственный проект при создании проекта
        # верхнего уровня (без parent)
        if dir_type == 'project' and not parent_id:
            pp = PPProject.objects.create(name=value, directory=entry)
            result['pp_project_id'] = pp.pk

        return JsonResponse(result, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class DirectoryDetailView(AdminRequiredJsonMixin, View):
    """
    PUT    -- обновление записи справочника.
    DELETE -- удаление записи с каскадным удалением потомков.
    """

    def put(self, request, pk):
        data = parse_json_body(request)
        value = data.get('value', '').strip()

        if not value:
            return JsonResponse(
                {'error': 'Поле value обязательно'}, status=400
            )

        try:
            entry = Directory.objects.get(pk=pk)
        except Directory.DoesNotExist:
            return JsonResponse(
                {'error': 'Запись не найдена'}, status=404
            )

        entry.value = value
        entry.save(update_fields=['value'])

        # Синхронизируем имя в PPProject, если это проект верхнего уровня
        if entry.dir_type == 'project' and not entry.parent_id:
            PPProject.objects.filter(directory=entry).update(name=value)

        return JsonResponse({'ok': True})

    def delete(self, request, pk):
        try:
            entry = Directory.objects.get(pk=pk)
        except Directory.DoesNotExist:
            return JsonResponse(
                {'error': 'Запись не найдена'}, status=404
            )

        is_top_project = (
            entry.dir_type == 'project' and not entry.parent_id
        )

        # Рекурсивный сбор всех потомков (BFS)
        to_delete_ids = [entry.pk]
        queue = [entry.pk]
        while queue:
            pid = queue.pop(0)
            children_ids = list(
                Directory.objects
                .filter(parent_id=pid)
                .values_list('id', flat=True)
            )
            to_delete_ids.extend(children_ids)
            queue.extend(children_ids)

        # Удаляем все найденные записи
        Directory.objects.filter(pk__in=to_delete_ids).delete()

        # Каскадное удаление производственного плана при удалении проекта
        if is_top_project:
            pp_projects = PPProject.objects.filter(directory_id=pk)
            for pp in pp_projects:
                # Удаляем связанные записи ПП
                pp.pp_works.all().delete()
                pp.delete()

        return JsonResponse({'ok': True})
