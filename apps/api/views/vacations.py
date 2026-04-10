"""
API для отпусков (Vacation).

CRUD-операции над таблицей Vacation + проверка пересечений.
GET     /api/vacations                 -- список отпусков (с фильтрами)
POST    /api/vacations                 -- создание отпуска (writer)
PUT     /api/vacations/<id>            -- обновление отпуска (writer)
DELETE  /api/vacations/<id>            -- удаление отпуска (writer)
POST    /api/check_vacation_conflict   -- проверка пересечений
"""

import logging
from datetime import date

from django.db.models import Q
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.api.utils import (
    build_employee_q,
    get_vacation_visibility_filter,
    resolve_employee_loose,
)
from apps.employees.models import Employee, Vacation

logger = logging.getLogger(__name__)

# Максимальное количество записей на странице
VACATIONS_MAX = 500


# ── GET / POST /api/vacations ────────────────────────────────────────────────


class VacationListView(LoginRequiredJsonMixin, View):
    """
    GET  -- список отпусков с фильтрами и пагинацией.
    POST -- создание нового отпуска (только writer).
    """

    def get(self, request):
        # Пагинация
        try:
            per_page = int(request.GET.get("per_page", 0)) or VACATIONS_MAX
            page = int(request.GET.get("page", 1))
        except (ValueError, TypeError):
            per_page, page = VACATIONS_MAX, 1
        per_page = min(per_page, VACATIONS_MAX)
        page = max(page, 1)
        offset = (page - 1) * per_page

        # Фильтр видимости по роли
        vis_q = get_vacation_visibility_filter(request.user)

        qs = Vacation.objects.filter(vis_q).select_related(
            "employee", "employee__department"
        )

        # Фильтр по отделу
        dept = request.GET.get("dept", "").strip()
        if dept:
            qs = qs.filter(employee__department__code=dept)

        # Фильтр по исполнителю (поиск по фамилии)
        executor = request.GET.get("executor", "").strip()
        if executor:
            qs = qs.filter(
                Q(employee__last_name__icontains=executor)
                | Q(employee__first_name__icontains=executor)
            )

        # Фильтр по году
        year = request.GET.get("year", "").strip()
        if year:
            try:
                yr = int(year)
                qs = qs.filter(date_start__year__lte=yr, date_end__year__gte=yr)
            except (ValueError, TypeError):
                pass

        qs = qs.order_by("date_start")

        rows = qs[offset : offset + per_page]
        result = []
        for v in rows:
            emp = v.employee
            result.append(
                {
                    "id": v.pk,
                    "executor": emp.full_name if emp else "",
                    "executor_name": emp.full_name if emp else "",
                    "date_start": v.date_start.isoformat() if v.date_start else "",
                    "date_end": v.date_end.isoformat() if v.date_end else "",
                    "notes": v.notes,
                    "dept": emp.department.code if emp and emp.department else "",
                    "position": (
                        emp.get_position_display() if emp and emp.position else ""
                    ),
                    "vac_type": v.vac_type,
                }
            )

        return JsonResponse(result, safe=False)


class VacationCreateView(WriterRequiredJsonMixin, View):
    """POST -- создание отпуска."""

    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)

        # Определяем сотрудника: по employee_id или по имени (executor)
        employee = None
        employee_id = data.get("employee_id")
        executor_name = data.get("executor", "").strip()

        if employee_id:
            try:
                employee = Employee.objects.get(pk=employee_id)
            except Employee.DoesNotExist:
                return JsonResponse({"error": "Сотрудник не найден"}, status=404)
        elif executor_name:
            # Нестрогий поиск по ФИО (ручной ввод из UI)
            employee = resolve_employee_loose(executor_name)

        date_start_str = data.get("date_start", "")
        date_end_str = data.get("date_end", "")
        notes = data.get("notes", "")
        vac_type = data.get("vac_type", Vacation.TYPE_ANNUAL)

        # Валидация дат
        if date_start_str and date_end_str:
            try:
                ds = date.fromisoformat(date_start_str)
                de = date.fromisoformat(date_end_str)
                if de < ds:
                    return JsonResponse(
                        {"error": "Дата окончания не может быть раньше даты начала"},
                        status=400,
                    )
            except (ValueError, TypeError):
                return JsonResponse({"error": "Неверный формат даты"}, status=400)
        else:
            ds = None
            de = None

        if employee:
            vacation = Vacation.objects.create(
                employee=employee,
                vac_type=vac_type,
                date_start=ds,
                date_end=de,
                notes=notes,
            )
        else:
            # Создаём запись без привязки к сотруднику (как во Flask --
            # пустые поля, потом заполняются через PUT)
            # Но Vacation.employee -- NOT NULL FK, поэтому нужен сотрудник.
            # Если не найден -- ошибка.
            return JsonResponse(
                {"error": "Не указан или не найден сотрудник (employee_id / executor)"},
                status=400,
            )

        return JsonResponse({"id": vacation.pk}, status=201)


# ── PUT / DELETE /api/vacations/<id> ─────────────────────────────────────────


class VacationDetailView(WriterRequiredJsonMixin, View):
    """
    PUT    -- обновление отпуска.
    DELETE -- удаление отпуска.
    """

    def put(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)
        if not data:
            return JsonResponse({"error": "Пустой запрос"}, status=400)

        # Проверка видимости: writer может редактировать только свою зону
        vis_q = get_vacation_visibility_filter(request.user)
        try:
            vacation = (
                Vacation.objects.select_related("employee").filter(vis_q).get(pk=pk)
            )
        except Vacation.DoesNotExist:
            return JsonResponse({"error": "Запись не найдена"}, status=404)

        # Фильтрация допустимых полей
        update_fields = []

        # executor -- меняем привязку к сотруднику по ФИО
        if "executor" in data:
            executor_name = data["executor"].strip()
            if executor_name:
                emp = resolve_employee_loose(executor_name)
                if emp:
                    vacation.employee = emp
                    update_fields.append("employee")

        if "employee_id" in data:
            try:
                emp = Employee.objects.get(pk=data["employee_id"])
                vacation.employee = emp
                update_fields.append("employee")
            except Employee.DoesNotExist:
                pass

        # date_start / date_end
        new_start = data.get("date_start")
        new_end = data.get("date_end")

        if new_start is not None:
            try:
                vacation.date_start = date.fromisoformat(new_start)
                update_fields.append("date_start")
            except (ValueError, TypeError):
                return JsonResponse({"error": "Неверный формат date_start"}, status=400)

        if new_end is not None:
            try:
                vacation.date_end = date.fromisoformat(new_end)
                update_fields.append("date_end")
            except (ValueError, TypeError):
                return JsonResponse({"error": "Неверный формат date_end"}, status=400)

        # Серверная валидация: date_end >= date_start
        if vacation.date_start and vacation.date_end:
            if vacation.date_end < vacation.date_start:
                return JsonResponse(
                    {"error": "Дата окончания не может быть раньше даты начала"},
                    status=400,
                )

        if "notes" in data:
            vacation.notes = data["notes"]
            update_fields.append("notes")

        if "vac_type" in data:
            vacation.vac_type = data["vac_type"]
            update_fields.append("vac_type")

        if update_fields:
            vacation.save(update_fields=update_fields + ["updated_at"])

        return JsonResponse({"ok": True})

    def delete(self, request, pk):
        # Проверка видимости: writer может удалять только свою зону
        vis_q = get_vacation_visibility_filter(request.user)
        try:
            vacation = Vacation.objects.filter(vis_q).get(pk=pk)
        except Vacation.DoesNotExist:
            return JsonResponse({"error": "Запись не найдена"}, status=404)

        vacation.delete()
        return JsonResponse({"ok": True})


# ── POST /api/check_vacation_conflict ────────────────────────────────────────


class VacationConflictView(LoginRequiredJsonMixin, View):
    """
    POST -- проверка пересечений с отпусками.
    Тело: {executors: [name, ...], date_start, date_end, exclude_id?}
    Ответ: {conflicts: [{executor, vacation_start, vacation_end}, ...]}
    """

    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)

        executors_raw = data.get("executors", [])
        date_start_str = data.get("date_start")
        date_end_str = data.get("date_end")
        exclude_id = data.get("exclude_id")

        if not executors_raw or not date_start_str or not date_end_str:
            return JsonResponse({"conflicts": []})

        # Нормализуем имена исполнителей
        exec_names = []
        for e in executors_raw:
            if isinstance(e, str):
                exec_names.append(e)
            elif isinstance(e, dict):
                name = e.get("name", "")
                if name:
                    exec_names.append(name)

        if not exec_names:
            return JsonResponse({"conflicts": []})

        try:
            ds = date.fromisoformat(date_start_str)
            de = date.fromisoformat(date_end_str)
        except (ValueError, TypeError):
            return JsonResponse({"conflicts": []})

        # Собираем Q для поиска сотрудников по ФИО
        # Собираем Q-фильтр для массового поиска сотрудников по списку ФИО
        emp_q = Q()
        for name in exec_names:
            q = build_employee_q(name)
            if q:
                emp_q |= q

        employee_ids = list(Employee.objects.filter(emp_q).values_list("pk", flat=True))

        if not employee_ids:
            return JsonResponse({"conflicts": []})

        # Пересечение: [start1, end1] vs [start2, end2]
        # start1 <= end2 AND end1 >= start2
        qs = Vacation.objects.filter(
            employee_id__in=employee_ids,
            date_start__lte=de,
            date_end__gte=ds,
        ).select_related("employee")

        if exclude_id:
            qs = qs.exclude(pk=exclude_id)

        conflicts = []
        for v in qs:
            conflicts.append(
                {
                    "id": v.pk,
                    "executor": v.employee.full_name if v.employee else "",
                    "date_start": v.date_start.isoformat() if v.date_start else "",
                    "date_end": v.date_end.isoformat() if v.date_end else "",
                    "notes": v.notes,
                }
            )

        return JsonResponse({"conflicts": conflicts})
