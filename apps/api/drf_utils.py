"""
Утилиты Django REST Framework.

Кастомный exception handler и permission-классы, совместимые
с форматом ответов существующего API: {"error": "сообщение"}.
"""

import logging

from django.utils import timezone
from rest_framework import permissions
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    ParseError,
    PermissionDenied,
    ValidationError,
)
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


# ── Exception Handler ─────────────────────────────────────────────────────────


def custom_exception_handler(exc, context):
    """
    Преобразует стандартные DRF-ошибки в формат {"error": "сообщение"},
    совместимый с существующим фронтендом.

    DRF по умолчанию возвращает {"detail": "..."}, наш фронтенд ожидает
    {"error": "..."} — этот обработчик обеспечивает совместимость.

    DRF SessionAuthentication возвращает 403 для неавторизованных — мы
    исправляем на 401 для совместимости с фронтендом.
    """
    # Если DRF бросил PermissionDenied, но пользователь не авторизован — это 401
    request = context.get("request")
    if isinstance(exc, (NotAuthenticated, PermissionDenied)):
        if request and not request.user.is_authenticated:
            exc = NotAuthenticated(detail="Не авторизован")

    # Вызываем стандартный обработчик DRF (обрабатывает Response и статус-код)
    response = exception_handler(exc, context)

    if response is not None:
        # Формируем единый формат сообщения об ошибке
        if isinstance(exc, ValidationError):
            # ValidationError может содержать вложенные ошибки по полям
            detail = exc.detail
            if isinstance(detail, dict):
                # {"field": ["error1", "error2"]} → "field: error1; error2"
                parts = []
                for field, errors in detail.items():
                    if isinstance(errors, list):
                        msg = "; ".join(str(e) for e in errors)
                    else:
                        msg = str(errors)
                    parts.append(f"{field}: {msg}")
                error_msg = "; ".join(parts)
            elif isinstance(detail, list):
                error_msg = "; ".join(str(e) for e in detail)
            else:
                error_msg = str(detail)
        elif isinstance(exc, NotAuthenticated):
            error_msg = "Не авторизован"
        elif isinstance(exc, AuthenticationFailed):
            error_msg = "Ошибка аутентификации"
        elif isinstance(exc, PermissionDenied):
            error_msg = str(exc.detail) if exc.detail else "Доступ запрещён"
        elif isinstance(exc, ParseError):
            error_msg = "Невалидный JSON"
        else:
            error_msg = str(getattr(exc, "detail", "Внутренняя ошибка сервера"))

        response.data = {"error": error_msg}

    return response


# ── Permissions ───────────────────────────────────────────────────────────────


class IsWriterPermission(permissions.BasePermission):
    """
    Проверяет, что пользователь — writer (по роли или делегированию).
    Аналог WriterRequiredJsonMixin.
    """

    message = "Нет прав на изменение данных"

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        employee = getattr(user, "employee", None)
        if not employee:
            return False

        # Роль writer — пропускаем
        if employee.is_writer:
            return True

        # Проверка делегирования с правом записи (кэш на запрос)
        if not hasattr(request, "_has_write_delegation"):
            from apps.employees.models import RoleDelegation

            request._has_write_delegation = RoleDelegation.objects.filter(
                delegate=employee,
                can_write=True,
                valid_until__gt=timezone.now(),
            ).exists()

        return request._has_write_delegation


class IsAdminPermission(permissions.BasePermission):
    """
    Проверяет, что пользователь — администратор.
    Аналог AdminRequiredJsonMixin.
    """

    message = "Нет прав администратора"

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        employee = getattr(user, "employee", None)
        return employee is not None and employee.role == "admin"
