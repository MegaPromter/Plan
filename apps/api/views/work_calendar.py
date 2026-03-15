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

from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    AdminRequiredJsonMixin,
    LoginRequiredJsonMixin,
    parse_json_body,
)
from apps.api.views.dependencies import invalidate_holiday_cache
from apps.works.models import Holiday, WorkCalendar

logger = logging.getLogger(__name__)

MONTH_NAMES_RU = [
    '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]


def _serialize(cal):
    return {
        'id': cal.id,
        'year': cal.year,
        'month': cal.month,
        'month_name': MONTH_NAMES_RU[cal.month] if 1 <= cal.month <= 12 else '',
        'hours_norm': float(cal.hours_norm),
        'month_key': cal.month_key,
    }


class WorkCalendarListView(LoginRequiredJsonMixin, View):
    """GET — список норм по году; POST create перенаправляется в WorkCalendarCreateView."""

    def get(self, request):
        try:
            qs = WorkCalendar.objects.all()
            year = request.GET.get('year')
            if year:
                try:
                    qs = qs.filter(year=int(year))
                except (ValueError, TypeError):
                    pass
            return JsonResponse([_serialize(c) for c in qs], safe=False)
        except Exception as e:
            logger.error('WorkCalendarListView.get error: %s', e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


class WorkCalendarCreateView(AdminRequiredJsonMixin, View):
    """POST — создание или обновление нормы на месяц (upsert по year+month)."""

    def post(self, request):
        try:
            d = parse_json_body(request)
            if d is None:
                return JsonResponse({'error': 'Невалидный JSON'}, status=400)
            year = d.get('year')
            month = d.get('month')
            hours_norm = d.get('hours_norm')

            try:
                year = int(year)
                month = int(month)
                hours_norm = float(hours_norm)
            except (TypeError, ValueError):
                return JsonResponse(
                    {'error': 'year, month и hours_norm обязательны и должны быть числами'},
                    status=400,
                )

            if not (1 <= month <= 12):
                return JsonResponse({'error': 'month должен быть от 1 до 12'}, status=400)
            if hours_norm < 0:
                return JsonResponse({'error': 'hours_norm не может быть отрицательным'}, status=400)
            if year < 2000 or year > 2100:
                return JsonResponse({'error': 'year должен быть от 2000 до 2100'}, status=400)

            cal, created = WorkCalendar.objects.update_or_create(
                year=year, month=month,
                defaults={'hours_norm': hours_norm},
            )
            return JsonResponse(_serialize(cal), status=201 if created else 200)
        except Exception as e:
            logger.error('WorkCalendarCreateView.post error: %s', e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


class WorkCalendarDetailView(AdminRequiredJsonMixin, View):
    """PUT /DELETE /api/work_calendar/<id>/"""

    def put(self, request, pk):
        try:
            cal = WorkCalendar.objects.filter(pk=pk).first()
            if not cal:
                return JsonResponse({'error': 'Запись не найдена'}, status=404)
            d = parse_json_body(request)
            if d is None:
                return JsonResponse({'error': 'Невалидный JSON'}, status=400)
            try:
                cal.hours_norm = float(d['hours_norm'])
            except (KeyError, TypeError, ValueError):
                return JsonResponse({'error': 'hours_norm обязателен'}, status=400)
            if cal.hours_norm < 0:
                return JsonResponse(
                    {'error': 'hours_norm не может быть отрицательным'}, status=400
                )
            cal.save(update_fields=['hours_norm'])
            return JsonResponse(_serialize(cal))
        except Exception as e:
            logger.error('WorkCalendarDetailView.put error: %s', e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

    def delete(self, request, pk):
        try:
            cal = WorkCalendar.objects.filter(pk=pk).first()
            if not cal:
                return JsonResponse({'error': 'Запись не найдена'}, status=404)
            cal.delete()
            return JsonResponse({'ok': True})
        except Exception as e:
            logger.error('WorkCalendarDetailView.delete error: %s', e, exc_info=True)
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


# ── Holiday API ──────────────────────────────────────────────────────────────


def _serialize_holiday(h):
    return {'id': h.id, 'date': str(h.date), 'name': h.name}


class HolidayListView(LoginRequiredJsonMixin, View):
    """GET — список праздников; POST — создание (admin)."""

    def get(self, request):
        qs = Holiday.objects.all()
        year = request.GET.get('year')
        if year:
            try:
                qs = qs.filter(date__year=int(year))
            except (ValueError, TypeError):
                pass
        return JsonResponse([_serialize_holiday(h) for h in qs], safe=False)

    def post(self, request):
        if not (request.user.is_superuser
                or getattr(getattr(request.user, 'employee', None), 'role', '') == 'admin'):
            return JsonResponse({'error': 'Только для администраторов'}, status=403)
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        date_str = d.get('date', '')
        name = d.get('name', '')
        try:
            holiday_date = dt_date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'date обязателен в формате YYYY-MM-DD'}, status=400)
        h, created = Holiday.objects.get_or_create(
            date=holiday_date, defaults={'name': name},
        )
        if not created:
            return JsonResponse({'error': 'Эта дата уже добавлена'}, status=409)
        invalidate_holiday_cache()
        return JsonResponse(_serialize_holiday(h), status=201)


class HolidayDetailView(AdminRequiredJsonMixin, View):
    """DELETE /api/holidays/<id>/"""

    def delete(self, request, pk):
        h = Holiday.objects.filter(pk=pk).first()
        if not h:
            return JsonResponse({'error': 'Запись не найдена'}, status=404)
        h.delete()
        invalidate_holiday_cache()
        return JsonResponse({'ok': True})
