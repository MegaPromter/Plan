"""
API для загрузки дампа данных из data_dump.json.
Защищён секретным ключом (env LOAD_DUMP_SECRET).

POST /api/load_dump/  { "secret": "..." }
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

    def post(self, request):
        # Проверка секрета
        import json
        try:
            body = json.loads(request.body or '{}')
        except (json.JSONDecodeError, ValueError):
            body = {}

        secret = body.get('secret', '')
        expected = os.environ.get('LOAD_DUMP_SECRET', '')
        if not expected or secret != expected:
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
