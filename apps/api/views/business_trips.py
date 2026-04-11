"""
API для командировок (BusinessTrip).

GET     /api/business_trips/          -- список командировок (с фильтрами)
POST    /api/business_trips/          -- создание (writer)
PUT     /api/business_trips/<id>/     -- обновление (writer)
DELETE  /api/business_trips/<id>/     -- удаление (writer)
"""

import logging
from datetime import date

from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.drf_utils import IsWriterPermission
from apps.api.utils import get_vacation_visibility_filter, resolve_employee_loose
from apps.employees.models import BusinessTrip, Employee

logger = logging.getLogger(__name__)

TRIPS_MAX = 500


def _serialize_trip(t):
    emp = t.employee
    return {
        "id": t.pk,
        "executor": emp.full_name if emp else "",
        "employee_id": emp.pk if emp else None,
        "dept": emp.department.code if emp and emp.department else "",
        "location": t.location,
        "purpose": t.purpose,
        "date_start": t.date_start.isoformat() if t.date_start else "",
        "date_end": t.date_end.isoformat() if t.date_end else "",
        "status": t.status,
        "status_display": t.get_status_display(),
        "notes": t.notes,
        "duration_days": t.duration_days,
    }


class BusinessTripListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            per_page = int(request.GET.get("per_page", 0)) or TRIPS_MAX
            page = int(request.GET.get("page", 1))
        except (ValueError, TypeError):
            per_page, page = TRIPS_MAX, 1
        per_page = min(per_page, TRIPS_MAX)
        page = max(page, 1)
        offset = (page - 1) * per_page

        vis_q = get_vacation_visibility_filter(request.user)

        qs = BusinessTrip.objects.filter(vis_q).select_related(
            "employee", "employee__department", "employee__department__ntc_center"
        )

        year = request.GET.get("year", "").strip()
        if year:
            try:
                qs = qs.filter(date_start__year=int(year))
            except (ValueError, TypeError):
                pass

        dept = request.GET.get("dept", "").strip()
        if dept:
            qs = qs.filter(employee__department__code=dept)

        status = request.GET.get("status", "").strip()
        if status:
            qs = qs.filter(status=status)

        executor = request.GET.get("executor", "").strip()
        if executor:
            qs = qs.filter(
                Q(employee__last_name__icontains=executor)
                | Q(employee__first_name__icontains=executor)
            )

        qs = qs.order_by("date_start")
        rows = qs[offset : offset + per_page]

        return Response([_serialize_trip(t) for t in rows])

    def post(self, request):
        emp = getattr(request.user, "employee", None)
        if not emp or not emp.is_writer:
            return Response({"error": "Недостаточно прав"}, status=403)

        data = request.data

        employee = None
        employee_id = data.get("employee_id")
        executor_name = data.get("executor", "").strip()

        if employee_id:
            try:
                employee = Employee.objects.get(pk=employee_id)
            except Employee.DoesNotExist:
                return Response({"error": "Сотрудник не найден"}, status=404)
        elif executor_name:
            employee = resolve_employee_loose(executor_name)

        if not employee:
            return Response({"error": "Не указан или не найден сотрудник"}, status=400)

        location = data.get("location", "").strip()
        purpose = data.get("purpose", "").strip()
        notes = data.get("notes", "")
        status_val = data.get("status", BusinessTrip.STATUS_PLAN)

        valid_statuses = {c[0] for c in BusinessTrip.STATUS_CHOICES}
        if status_val not in valid_statuses:
            return Response({"error": f"Недопустимый статус: {status_val}"}, status=400)

        ds_str = data.get("date_start", "")
        de_str = data.get("date_end", "")

        if not ds_str or not de_str:
            return Response({"error": "Даты обязательны"}, status=400)
        if not location:
            return Response({"error": "Место назначения обязательно"}, status=400)

        try:
            ds = date.fromisoformat(ds_str)
            de = date.fromisoformat(de_str)
            if de < ds:
                return Response(
                    {"error": "Дата окончания раньше даты начала"}, status=400
                )
        except (ValueError, TypeError):
            return Response({"error": "Неверный формат даты"}, status=400)

        trip = BusinessTrip.objects.create(
            employee=employee,
            location=location,
            purpose=purpose,
            date_start=ds,
            date_end=de,
            status=status_val,
            notes=notes,
        )
        return Response(_serialize_trip(trip), status=201)


class BusinessTripDetailView(APIView):
    http_method_names = ["put", "delete"]

    permission_classes = [IsWriterPermission]

    def put(self, request, pk):
        data = request.data
        if not data:
            return Response({"error": "Пустой запрос"}, status=400)

        vis_q = get_vacation_visibility_filter(request.user)
        try:
            trip = (
                BusinessTrip.objects.select_related("employee").filter(vis_q).get(pk=pk)
            )
        except BusinessTrip.DoesNotExist:
            return Response({"error": "Запись не найдена"}, status=404)

        update_fields = []

        if "employee_id" in data:
            try:
                emp = Employee.objects.get(pk=data["employee_id"])
                trip.employee = emp
                update_fields.append("employee")
            except Employee.DoesNotExist:
                return Response({"error": "Сотрудник не найден"}, status=404)

        if "status" in data:
            valid_statuses = {c[0] for c in BusinessTrip.STATUS_CHOICES}
            if data["status"] not in valid_statuses:
                return Response(
                    {"error": f'Недопустимый статус: {data["status"]}'}, status=400
                )

        for field in ("location", "purpose", "notes", "status"):
            if field in data:
                setattr(trip, field, data[field])
                update_fields.append(field)

        if "date_start" in data:
            try:
                trip.date_start = date.fromisoformat(data["date_start"])
                update_fields.append("date_start")
            except (ValueError, TypeError):
                return Response({"error": "Неверный формат date_start"}, status=400)

        if "date_end" in data:
            try:
                trip.date_end = date.fromisoformat(data["date_end"])
                update_fields.append("date_end")
            except (ValueError, TypeError):
                return Response({"error": "Неверный формат date_end"}, status=400)

        if trip.date_start and trip.date_end and trip.date_end < trip.date_start:
            return Response({"error": "Дата окончания раньше даты начала"}, status=400)

        if update_fields:
            trip.save(update_fields=update_fields + ["updated_at"])

        return Response(_serialize_trip(trip))

    def delete(self, request, pk):
        vis_q = get_vacation_visibility_filter(request.user)
        try:
            trip = BusinessTrip.objects.filter(vis_q).get(pk=pk)
        except BusinessTrip.DoesNotExist:
            return Response({"error": "Запись не найдена"}, status=404)

        trip.delete()
        return Response({"ok": True})
