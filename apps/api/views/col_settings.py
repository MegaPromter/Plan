"""
API для настроек колонок пользователя.

POST    /api/col_settings  -- сохранение настроек видимости столбцов
"""

# JsonResponse — HTTP-ответ с JSON-телом
from django.http import JsonResponse

# View — базовый класс для CBV
from django.views import View

# Миксин авторизации (требует входа) и парсер JSON-тела запроса
from apps.api.mixins import LoginRequiredJsonMixin, parse_json_body


class ColSettingsView(LoginRequiredJsonMixin, View):
    """
    POST -- сохранение настроек видимости столбцов.
    Принимает JSON-объект с настройками и записывает в employee.col_settings.
    """

    # Лимит ключей в одном запросе (защита от DoS — гигантский JSON)
    _MAX_KEYS = 100
    # Лимит длины имени ключа (защита от переполнения)
    _MAX_KEY_LEN = 64
    # Валидация имён ключей: только безопасные символы (защита от инъекций в БД)
    _KEY_RE = __import__("re").compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")

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
            # Нет профиля Employee — невозможно сохранить настройки
            return JsonResponse({"error": "Профиль сотрудника не найден"}, status=400)

        # Парсим JSON-тело запроса (получаем словарь настроек)
        incoming = parse_json_body(request)
        if incoming is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)

        # Валидация ключей
        key_err = self._validate_keys(incoming)
        if key_err:
            return JsonResponse({"error": key_err}, status=400)

        # Специальный флаг: сброс ширин колонок
        # Сохраняем только «не-ширинные» ключи (show_all_depts и т.п.)
        if incoming.get("_reset_widths"):
            # Получаем текущие настройки
            current = employee.col_settings or {}
            # Оставляем только ключи, не относящиеся к ширинам колонок
            # (ширины — это числовые значения вида 'col_work_name': 200)
            preserved = {
                k: v
                for k, v in current.items()
                if k in ("show_all_depts", "pp_input_modal")
            }
            # Перезаписываем настройки без ширин
            employee.col_settings = preserved
            # Сохраняем только поле col_settings (оптимизация UPDATE)
            employee.save(update_fields=["col_settings"])
            return JsonResponse({"ok": True})

        # Обычное обновление: merge с существующими настройками
        # (не заменяем весь объект, а дополняем/перезаписываем только переданные ключи)
        current = employee.col_settings or {}
        # Мержим входящие настройки поверх существующих
        current.update(incoming or {})
        employee.col_settings = current
        # Сохраняем только поле col_settings
        employee.save(update_fields=["col_settings"])

        return JsonResponse({"ok": True})
