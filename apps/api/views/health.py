"""Health check endpoint для мониторинга и балансировщиков."""

from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """GET /api/health/ — проверка состояния приложения и БД."""

    # Публичный endpoint — не требует авторизации
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return Response({"status": "ok"})
        except Exception:
            return Response(
                {"status": "error", "error": "database unavailable"}, status=503
            )
