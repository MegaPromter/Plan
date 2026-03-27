"""Health check endpoint для мониторинга и балансировщиков."""
from django.db import connection
from django.http import JsonResponse
from django.views import View


class HealthCheckView(View):
    """GET /api/health/ — проверка состояния приложения и БД."""

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            return JsonResponse({'status': 'ok'})
        except Exception:
            return JsonResponse({'status': 'error', 'error': 'database unavailable'}, status=503)
