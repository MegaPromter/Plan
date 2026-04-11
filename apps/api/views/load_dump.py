"""
API для загрузки дампа данных из data_dump.json.
Защищён секретным ключом (env LOAD_DUMP_SECRET).

POST /api/load_dump/  { "secret": "..." }
GET  /api/load_dump/  — диагностика (показывает состояние)
"""

import logging
import os

from django.conf import settings
from django.core.management import call_command
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

DUMP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data_dump.json",
)


@method_decorator(csrf_exempt, name="dispatch")
class LoadDumpView(APIView):
    """POST — загрузить данные из data_dump.json (требует секрет, только DEBUG)."""

    permission_classes = [AllowAny]

    def post(self, request):
        # Эндпоинт доступен только в режиме отладки
        if not settings.DEBUG:
            return Response({"error": "Недоступно"}, status=404)
        # Проверка секрета
        import json

        try:
            body = json.loads(request.body or "{}")
        except (json.JSONDecodeError, ValueError):
            body = {}

        expected_secret = os.environ.get("LOAD_DUMP_SECRET", "")
        if not expected_secret:
            logger.error("load_dump: LOAD_DUMP_SECRET не настроен")
            return Response({"error": "Endpoint не настроен"}, status=500)
        secret = body.get("secret", "").strip()
        if secret != expected_secret:
            return Response({"error": "Forbidden"}, status=403)

        # Проверяем наличие файла
        if not os.path.isfile(DUMP_FILE):
            return Response(
                {"error": f"Файл {DUMP_FILE} не найден"},
                status=404,
            )

        try:
            # flush очищает БД
            logger.info("load_dump: flushing database...")
            call_command("flush", "--noinput")

            # loaddata загружает данные
            logger.info("load_dump: loading data from %s", DUMP_FILE)
            call_command("loaddata", DUMP_FILE)

            logger.info("load_dump: done")
            return Response({"ok": True, "message": "Данные загружены"})
        except Exception as e:
            logger.exception("load_dump: error")
            return Response({"error": str(e)}, status=500)
