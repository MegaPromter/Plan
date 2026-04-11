"""
API для настроек колонок пользователя.

POST    /api/col_settings  -- сохранение настроек видимости столбцов
"""

import re

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class ColSettingsView(APIView):
    """
    POST -- сохранение настроек видимости столбцов.
    Принимает JSON-объект с настройками и записывает в employee.col_settings.
    """

    permission_classes = [IsAuthenticated]

    # Лимит ключей в одном запросе (защита от DoS — гигантский JSON)
    _MAX_KEYS = 100
    # Лимит длины имени ключа (защита от переполнения)
    _MAX_KEY_LEN = 64
    # Валидация имён ключей: только безопасные символы (защита от инъекций в БД)
    _KEY_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")

    @classmethod
    def _validate_keys(cls, data):
        """Проверяет ключи на допустимость. Возвращает строку ошибки или None."""
        if len(data) > cls._MAX_KEYS:
            return f"Слишком много ключей (максимум {cls._MAX_KEYS})"
        for key in data:
            if not isinstance(key, str):
                return "Ключ должен быть строкой"
            if len(key) > cls._MAX_KEY_LEN:
                return f"Ключ слишком длинный: {key[:20]}..."
            if not cls._KEY_RE.match(key):
                return f"Недопустимый ключ: {key}"
        return None

    def post(self, request):
        # Получаем профиль сотрудника, привязанный к пользователю
        employee = getattr(request.user, "employee", None)
        if not employee:
            return Response({"error": "Профиль сотрудника не найден"}, status=400)

        # request.data — DRF автоматически парсит JSON из тела запроса
        incoming = request.data
        if not isinstance(incoming, dict):
            return Response({"error": "Невалидный JSON"}, status=400)

        # Валидация ключей
        key_err = self._validate_keys(incoming)
        if key_err:
            return Response({"error": key_err}, status=400)

        # Специальный флаг: сброс ширин колонок
        if incoming.get("_reset_widths"):
            current = employee.col_settings or {}
            preserved = {
                k: v
                for k, v in current.items()
                if k in ("show_all_depts", "pp_input_modal")
            }
            employee.col_settings = preserved
            employee.save(update_fields=["col_settings"])
            return Response({"ok": True})

        # Обычное обновление: merge с существующими настройками
        current = employee.col_settings or {}
        current.update(incoming or {})
        employee.col_settings = current
        employee.save(update_fields=["col_settings"])

        return Response({"ok": True})
