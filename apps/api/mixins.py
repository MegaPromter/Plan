"""
Миксины для API-вьюх.
Аналог Flask-декораторов login_required, admin_required, write_required.
"""
# Стандартный модуль для работы с JSON
import json
# functools.wraps — сохраняет метаданные декорируемой функции
from functools import wraps

# JsonResponse — возвращает HTTP-ответ с JSON-телом
from django.http import JsonResponse
# timezone — работа с датой/временем с учётом часового пояса
from django.utils import timezone
# View — базовый класс для class-based views в Django
from django.views import View

# Модель делегирования ролей (временные права на запись)
from apps.employees.models import RoleDelegation


class LoginRequiredJsonMixin:
    """Возвращает 401 JSON вместо redirect для API-запросов."""

    def dispatch(self, request, *args, **kwargs):
        # Проверяем, авторизован ли пользователь
        if not request.user.is_authenticated:
            # Если нет — возвращаем JSON с ошибкой 401 (не авторизован)
            return JsonResponse({"error": "Не авторизован"}, status=401)
        # Пользователь авторизован — передаём управление дальше по MRO
        return super().dispatch(request, *args, **kwargs)


class WriterRequiredJsonMixin(LoginRequiredJsonMixin):
    """
    Проверяет, что пользователь — writer (роль из WRITER_ROLES)
    или имеет активное делегирование с правом записи.
    """

    def dispatch(self, request, *args, **kwargs):
        # Сначала проверяем авторизацию (до проверки прав)
        if not request.user.is_authenticated:
            # Неавторизованный пользователь — 401
            return JsonResponse({"error": "Не авторизован"}, status=401)

        # Получаем профиль Employee, привязанный к пользователю (может быть None)
        employee = getattr(request.user, 'employee', None)
        if employee and employee.is_writer:
            # Пользователь имеет роль writer — пропускаем без проверки делегирований
            # Вызываем dispatch родителя LoginRequiredJsonMixin — то есть View.dispatch
            return super(LoginRequiredJsonMixin, self).dispatch(
                request, *args, **kwargs
            )

        # Проверяем делегирования с правом записи
        if employee:
            # Ищем активное делегирование: delegate=текущий сотрудник,
            # can_write=True, срок действия ещё не истёк
            has_write = RoleDelegation.objects.filter(
                delegate=employee,
                can_write=True,
                valid_until__gt=timezone.now(),
            ).exists()
            if has_write:
                # Найдено активное делегирование — допускаем запрос
                return super(LoginRequiredJsonMixin, self).dispatch(
                    request, *args, **kwargs
                )

        # Ни роль writer, ни делегирование не подтверждены — 403
        return JsonResponse(
            {"error": "Нет прав на изменение данных"}, status=403
        )


class AdminRequiredJsonMixin(LoginRequiredJsonMixin):
    """Проверяет, что пользователь — администратор."""

    def dispatch(self, request, *args, **kwargs):
        # Проверяем авторизацию
        if not request.user.is_authenticated:
            # Не авторизован — 401
            return JsonResponse({"error": "Не авторизован"}, status=401)

        # Получаем профиль Employee
        employee = getattr(request.user, 'employee', None)
        if not employee or employee.role != 'admin':
            # Нет профиля или роль не admin — 403
            return JsonResponse(
                {"error": "Нет прав администратора"}, status=403
            )
        # Роль admin подтверждена — пропускаем запрос дальше по MRO
        return super(LoginRequiredJsonMixin, self).dispatch(
            request, *args, **kwargs
        )


def parse_json_body(request):
    """Парсит JSON из тела запроса.
    Возвращает dict, пустой dict (если тело пустое) или None (при невалидном JSON)."""
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        # Невалидный JSON — возвращаем None, чтобы caller мог вернуть 400
        return None
