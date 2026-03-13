"""
API для загрузки дампа данных из data_dump.json.
Защищён секретным ключом (env LOAD_DUMP_SECRET).

POST /api/load_dump/  { "secret": "..." }
GET  /api/load_dump/  — диагностика (показывает состояние)
"""
import os
import logging

from django.core.management import call_command
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

DUMP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    'data_dump.json',
)


@method_decorator(csrf_exempt, name='dispatch')
class LoadDumpView(View):
    """POST — загрузить данные из data_dump.json (требует секрет)."""

    def get(self, request):
        """Диагностика: показать состояние переменных и файла."""
        expected = os.environ.get('LOAD_DUMP_SECRET', '')
        return JsonResponse({
            'dump_file': DUMP_FILE,
            'dump_exists': os.path.isfile(DUMP_FILE),
            'secret_configured': bool(expected),
        })

    def post(self, request):
        # Проверка секрета
        import json
        try:
            body = json.loads(request.body or '{}')
        except (json.JSONDecodeError, ValueError):
            body = {}

        expected_secret = os.environ.get('LOAD_DUMP_SECRET', '')
        secret = body.get('secret', '').strip()
        if not expected_secret or secret != expected_secret:
            return JsonResponse({'error': 'Forbidden'}, status=403)

        # Проверяем наличие файла
        if not os.path.isfile(DUMP_FILE):
            return JsonResponse(
                {'error': f'Файл {DUMP_FILE} не найден'}, status=404,
            )

        try:
            # flush очищает БД
            logger.info('load_dump: flushing database...')
            call_command('flush', '--noinput')

            # loaddata загружает данные
            logger.info('load_dump: loading data from %s', DUMP_FILE)
            call_command('loaddata', DUMP_FILE)

            logger.info('load_dump: done')
            return JsonResponse({'ok': True, 'message': 'Данные загружены'})
        except Exception as e:
            logger.exception('load_dump: error')
            return JsonResponse({'error': str(e)}, status=500)
