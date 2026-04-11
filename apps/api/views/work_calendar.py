"""
API производственного календаря (WorkCalendar + Holiday).

GET    /api/work_calendar/         — список записей (все авторизованные)
POST   /api/work_calendar/create/  — создание / обновление записи (admin)
PUT    /api/work_calendar/<id>/    — обновление нормы часов (admin)
DELETE /api/work_calendar/<id>/    — удаление записи (admin)

GET    /api/holidays/              — список праздников (все авторизованные)
POST   /api/holidays/              — создание праздника (admin)
DELETE /api/holidays/<id>/         — удаление праздника (admin)
"""

import logging
from datetime import date as dt_date

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.drf_utils import IsAdminPermission
from apps.api.views.dependencies import invalidate_holiday_cache
from apps.works.models import Holiday, WorkCalendar

logger = logging.getLogger(__name__)

MONTH_NAMES_RU = [
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]


def _serialize(cal):
    return {
        "id": cal.id,
        "year": cal.year,
        "month": cal.month,
        "month_name": MONTH_NAMES_RU[cal.month] if 1 <= cal.month <= 12 else "",
        "hours_norm": float(cal.hours_norm),
        "month_key": cal.month_key,
    }


class WorkCalendarListView(APIView):
    """GET — список норм по году."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = WorkCalendar.objects.all()
            year = request.GET.get("year")
            if year:
                try:
                    qs = qs.filter(year=int(year))
                except (ValueError, TypeError):
                    pass
            return Response([_serialize(c) for c in qs])
        except Exception as e:
            logger.error("WorkCalendarListView.get error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)


class WorkCalendarCreateView(APIView):
    """POST — создание или обновление нормы на месяц (upsert по year+month)."""

    permission_classes = [IsAdminPermission]

    def post(self, request):
        try:
            d = request.data
            year = d.get("year")
            month = d.get("month")
            hours_norm = d.get("hours_norm")

            try:
                year = int(year)
                month = int(month)
                hours_norm = float(hours_norm)
            except (TypeError, ValueError):
                return Response(
                    {
                        "error": "year, month и hours_norm обязательны и должны быть числами"
                    },
                    status=400,
                )

            if not (1 <= month <= 12):
                return Response({"error": "month должен быть от 1 до 12"}, status=400)
            if hours_norm < 0:
                return Response(
                    {"error": "hours_norm не может быть отрицательным"}, status=400
                )
            if year < 2000 or year > 2100:
                return Response(
                    {"error": "year должен быть от 2000 до 2100"}, status=400
                )

            cal, created = WorkCalendar.objects.update_or_create(
                year=year,
                month=month,
                defaults={"hours_norm": hours_norm},
            )
            return Response(_serialize(cal), status=201 if created else 200)
        except Exception as e:
            logger.error("WorkCalendarCreateView.post error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)


class WorkCalendarDetailView(APIView):
    """PUT /DELETE /api/work_calendar/<id>/"""

    permission_classes = [IsAdminPermission]

    def put(self, request, pk):
        try:
            try:
                cal = WorkCalendar.objects.get(pk=pk)
            except WorkCalendar.DoesNotExist:
                return Response({"error": "Запись не найдена"}, status=404)
            d = request.data
            try:
                cal.hours_norm = float(d["hours_norm"])
            except (KeyError, TypeError, ValueError):
                return Response({"error": "hours_norm обязателен"}, status=400)
            if cal.hours_norm < 0:
                return Response(
                    {"error": "hours_norm не может быть отрицательным"}, status=400
                )
            cal.save(update_fields=["hours_norm"])
            return Response(_serialize(cal))
        except Exception as e:
            logger.error("WorkCalendarDetailView.put error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def delete(self, request, pk):
        try:
            try:
                cal = WorkCalendar.objects.get(pk=pk)
            except WorkCalendar.DoesNotExist:
                return Response({"error": "Запись не найдена"}, status=404)
            cal.delete()
            return Response({"ok": True})
        except Exception as e:
            logger.error("WorkCalendarDetailView.delete error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)


# ── Holiday API ──────────────────────────────────────────────────────────────


def _serialize_holiday(h):
    return {"id": h.id, "date": str(h.date), "name": h.name}


class HolidayListView(APIView):
    """GET — список праздников; POST — создание (admin)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Holiday.objects.all()
        year = request.GET.get("year")
        if year:
            try:
                qs = qs.filter(date__year=int(year))
            except (ValueError, TypeError):
                pass
        return Response([_serialize_holiday(h) for h in qs])

    def post(self, request):
        if not (
            request.user.is_superuser
            or getattr(getattr(request.user, "employee", None), "role", "") == "admin"
        ):
            return Response({"error": "Только для администраторов"}, status=403)
        d = request.data
        date_str = d.get("date", "")
        name = d.get("name", "")
        try:
            holiday_date = dt_date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return Response(
                {"error": "date обязателен в формате YYYY-MM-DD"}, status=400
            )
        h, created = Holiday.objects.get_or_create(
            date=holiday_date,
            defaults={"name": name},
        )
        if not created:
            return Response({"error": "Эта дата уже добавлена"}, status=409)
        invalidate_holiday_cache()
        return Response(_serialize_holiday(h), status=201)


class HolidayDetailView(APIView):
    """DELETE /api/holidays/<id>/"""

    permission_classes = [IsAdminPermission]

    def delete(self, request, pk):
        try:
            h = Holiday.objects.get(pk=pk)
        except Holiday.DoesNotExist:
            return Response({"error": "Запись не найдена"}, status=404)
        h.delete()
        invalidate_holiday_cache()
        return Response({"ok": True})
