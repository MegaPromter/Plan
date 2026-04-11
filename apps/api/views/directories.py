"""
API для справочников (directories).

CRUD-операции над универсальной таблицей Directory.
GET     /api/directories          -- список справочников (+ виртуальные employees)
POST    /api/directories          -- создание записи (admin)
PUT     /api/directories/<id>     -- обновление записи (admin)
DELETE  /api/directories/<id>     -- удаление записи (admin)
"""

import logging
from collections import defaultdict, deque

from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.drf_utils import IsAdminPermission
from apps.api.utils import short_name
from apps.employees.models import Department, Employee, NTCCenter, Sector
from apps.works.models import Directory, PPProject, Project, Work

logger = logging.getLogger(__name__)

DIRECTORIES_CACHE_KEY = "directories_list"
DIRECTORIES_CACHE_TTL = 300


# ── GET /api/directories ─────────────────────────────────────────────────────


class DirectoryListView(APIView):
    """
    GET  -- возвращает все записи справочника, сгруппированные по типу.
           Дополнительно формирует виртуальный справочник employees
           (ФИО + подразделение) для выпадающих списков.
    """

    permission_classes = [IsAuthenticated]

    _REAL_MODEL_TYPES = {"center", "dept", "sector", "task_type"}

    def get(self, request):
        cached = cache.get(DIRECTORIES_CACHE_KEY)
        if cached is not None:
            response = Response(cached)
            response["Cache-Control"] = "max-age=60"
            return response

        qs = Directory.objects.exclude(
            dir_type__in=self._REAL_MODEL_TYPES,
        ).order_by("dir_type", "value")

        result = defaultdict(list)
        for d in qs:
            result[d.dir_type].append(
                {
                    "id": d.pk,
                    "value": d.value,
                    "parent_id": d.parent_id,
                }
            )

        result["center"] = [
            {"id": c.pk, "value": c.code, "parent_id": None}
            for c in NTCCenter.objects.order_by("code")
        ]
        result["dept"] = [
            {"id": d.pk, "value": d.code, "parent_id": None}
            for d in Department.objects.order_by("code")
        ]

        sector_heads = {}
        for emp in Employee.objects.filter(
            role=Employee.ROLE_SECTOR_HEAD
        ).select_related("sector"):
            if emp.sector:
                sector_heads[emp.sector.code] = short_name(emp.full_name)

        result["sector"] = [
            {
                "id": s.pk,
                "value": s.code,
                "parent_id": s.department_id,
                "head_name": sector_heads.get(s.code, ""),
            }
            for s in Sector.objects.select_related("department").order_by(
                "department__code", "code"
            )
        ]

        emp_qs = (
            Employee.objects.exclude(last_name="")
            .select_related("department", "sector")
            .order_by("last_name", "first_name")
        )
        employees = []
        for emp in emp_qs:
            full = emp.full_name
            dept_code = emp.department.code if emp.department else ""
            sector_code = emp.sector.code if emp.sector else ""
            position = emp.get_position_display() if emp.position else ""
            abbrev = emp.short_name
            employees.append(
                {
                    "id": emp.pk,
                    "value": abbrev if abbrev else full,
                    "dept": dept_code,
                    "sector": sector_code,
                    "position": position,
                }
            )

        result["project"] = [
            {"id": p.pk, "value": p.name, "parent_id": None}
            for p in Project.objects.order_by("name_short", "name_full")
        ]

        from apps.works.models import PPStage

        result["stage"] = [
            {
                "id": s.id,
                "value": s.stage_number or s.name,
                "label": f"{s.stage_number}. {s.name}" if s.stage_number else s.name,
                "project_id": s.project_id,
                "row_code": s.row_code or "",
                "work_order": s.work_order or "",
                "parent_id": None,
            }
            for s in PPStage.objects.select_related("project").order_by(
                "project_id", "order", "id"
            )
        ]

        _TASK_TYPES = [
            "Выпуск нового документа",
            "Корректировка документа",
            "Разработка",
            "Сопровождение (ОКАН)",
        ]
        result["task_type"] = [
            {"id": idx, "value": v, "parent_id": None}
            for idx, v in enumerate(_TASK_TYPES, start=1)
        ]

        result["employees"] = employees

        payload = dict(result)
        cache.set(DIRECTORIES_CACHE_KEY, payload, DIRECTORIES_CACHE_TTL)

        response = Response(payload)
        response["Cache-Control"] = "max-age=60"
        return response


# ── POST / PUT / DELETE /api/directories ─────────────────────────────────────


class DirectoryCreateView(APIView):
    """POST -- создание записи справочника. Только admin."""

    permission_classes = [IsAdminPermission]

    def post(self, request):
        data = request.data
        if not isinstance(data, dict):
            return Response({"error": "Невалидный JSON"}, status=400)

        dir_type = data.get("type", "").strip()
        value = data.get("value", "").strip()
        parent_id = data.get("parent_id")

        if not dir_type or not value:
            return Response({"error": "Поля type и value обязательны"}, status=400)

        if dir_type in DirectoryListView._REAL_MODEL_TYPES:
            return Response(
                {"error": f'Тип "{dir_type}" управляется через модули подразделений'},
                status=400,
            )

        parent = None
        if parent_id:
            try:
                parent = Directory.objects.get(pk=parent_id)
            except Directory.DoesNotExist:
                return Response({"error": "Родительская запись не найдена"}, status=404)

        entry = Directory.objects.create(
            dir_type=dir_type,
            value=value,
            parent=parent,
        )

        cache.delete(DIRECTORIES_CACHE_KEY)

        result = {"id": entry.pk}

        if dir_type == "project" and not parent_id:
            pp = PPProject.objects.create(name=value, directory=entry)
            result["pp_project_id"] = pp.pk

        return Response(result, status=201)


class DirectoryDetailView(APIView):
    """
    PUT    -- обновление записи справочника.
    DELETE -- удаление записи с каскадным удалением потомков.
    """

    permission_classes = [IsAdminPermission]

    def put(self, request, pk):
        data = request.data
        if not isinstance(data, dict):
            return Response({"error": "Невалидный JSON"}, status=400)
        value = data.get("value", "").strip()

        if not value:
            return Response({"error": "Поле value обязательно"}, status=400)

        try:
            entry = Directory.objects.get(pk=pk)
        except Directory.DoesNotExist:
            return Response({"error": "Запись не найдена"}, status=404)

        entry.value = value
        entry.save(update_fields=["value"])

        cache.delete(DIRECTORIES_CACHE_KEY)

        if entry.dir_type == "project" and not entry.parent_id:
            PPProject.objects.filter(directory=entry).update(name=value)

        return Response({"ok": True})

    def delete(self, request, pk):
        try:
            entry = Directory.objects.get(pk=pk)
        except Directory.DoesNotExist:
            return Response({"error": "Запись не найдена"}, status=404)

        is_top_project = entry.dir_type == "project" and not entry.parent_id

        to_delete_ids = [entry.pk]
        bfs_queue = deque([entry.pk])
        while bfs_queue:
            pid = bfs_queue.popleft()
            children_ids = list(
                Directory.objects.filter(parent_id=pid).values_list("id", flat=True)
            )
            to_delete_ids.extend(children_ids)
            bfs_queue.extend(children_ids)

        if is_top_project:
            from django.db import transaction

            pp_projects = list(PPProject.objects.filter(directory_id=pk))
            if pp_projects:
                with transaction.atomic():
                    Work.objects.filter(pp_project__in=pp_projects).delete()
                    PPProject.objects.filter(
                        pk__in=[pp.pk for pp in pp_projects]
                    ).delete()

        Directory.objects.filter(pk__in=to_delete_ids).delete()

        cache.delete(DIRECTORIES_CACHE_KEY)

        return Response({"ok": True})
