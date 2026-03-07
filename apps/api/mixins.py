"""
Миксины для API-вьюх.
Аналог Flask-декораторов login_required, admin_required, write_required.
"""
import json
from functools import wraps

from django.http import JsonResponse
from django.utils import timezone
from django.views import View

from apps.employees.models import RoleDelegation


class LoginRequiredJsonMixin:
    """Возвращает 401 JSON вместо redirect для API-запросов."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Не авторизован"}, status=401)
        return super().dispatch(request, *args, **kwargs)


class WriterRequiredJsonMixin(LoginRequiredJsonMixin):
    """
    Проверяет, что пользователь — writer (роль из WRITER_ROLES)
    или имеет активное делегирование с правом записи.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Не авторизован"}, status=401)

        employee = getattr(request.user, 'employee', None)
        if employee and employee.is_writer:
            return super(LoginRequiredJsonMixin, self).dispatch(
                request, *args, **kwargs
            )

        # Проверяем делегирования с правом записи
        if employee:
            has_write = RoleDelegation.objects.filter(
                delegate=employee,
                can_write=True,
                valid_until__gt=timezone.now(),
            ).exists()
            if has_write:
                return super(LoginRequiredJsonMixin, self).dispatch(
                    request, *args, **kwargs
                )

        return JsonResponse(
            {"error": "Нет прав на изменение данных"}, status=403
        )


class AdminRequiredJsonMixin(LoginRequiredJsonMixin):
    """Проверяет, что пользователь — администратор."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Не авторизован"}, status=401)

        employee = getattr(request.user, 'employee', None)
        if not employee or employee.role != 'admin':
            return JsonResponse(
                {"error": "Нет прав администратора"}, status=403
            )
        return super(LoginRequiredJsonMixin, self).dispatch(
            request, *args, **kwargs
        )


def parse_json_body(request):
    """Парсит JSON из тела запроса. Возвращает dict или пустой dict."""
    try:
        return json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        return {}
