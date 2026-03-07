"""
API для настроек колонок пользователя.

POST    /api/col_settings  -- сохранение настроек видимости столбцов
"""
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.api.mixins import LoginRequiredJsonMixin, parse_json_body


@method_decorator(csrf_exempt, name='dispatch')
class ColSettingsView(LoginRequiredJsonMixin, View):
    """
    POST -- сохранение настроек видимости столбцов.
    Принимает JSON-объект с настройками и записывает в employee.col_settings.
    """

    def post(self, request):
        employee = getattr(request.user, 'employee', None)
        if not employee:
            return JsonResponse(
                {'error': 'Профиль сотрудника не найден'}, status=400
            )

        incoming = parse_json_body(request)

        # Специальный флаг: сброс ширин колонок
        # Сохраняем только «не-ширинные» ключи (show_all_depts и т.п.)
        if incoming.get('_reset_widths'):
            current = employee.col_settings or {}
            preserved = {k: v for k, v in current.items()
                         if k in ('show_all_depts',)}
            employee.col_settings = preserved
            employee.save(update_fields=['col_settings'])
            return JsonResponse({'ok': True})

        # Обычное обновление: merge с существующими настройками
        current = employee.col_settings or {}
        current.update(incoming or {})
        employee.col_settings = current
        employee.save(update_fields=['col_settings'])

        return JsonResponse({'ok': True})
