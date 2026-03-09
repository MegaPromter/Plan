"""
Rate-limiting middleware для защиты API от брутфорса.

Ограничения:
- /accounts/login/       : 10 попыток / 60 сек с одного IP
- /api/register_public/  : 5 попыток / 300 сек с одного IP
- /api/                  : 300 запросов / 60 сек с одного IP (общий лимит)
"""
# Модуль для работы с временем (используется для скользящего окна)
import time
# Стандартный логгер Python
import logging
# Django cache — используется для хранения счётчиков запросов (Redis/LocMem)
from django.core.cache import cache
# JsonResponse — для возврата JSON-ошибки при превышении лимита
from django.http import JsonResponse
# method_decorator — вспомогательный декоратор (импортирован, но не используется здесь напрямую)
from django.utils.decorators import method_decorator

# Логгер для данного модуля
logger = logging.getLogger(__name__)

# Правила ограничения запросов:
# (ключ-префикс, URL-префикс, макс.запросов, окно в секундах, is_api)
# is_api=True — вернуть JSON 429; is_api=False — вернуть HTML-текст 429
_RATE_RULES = [
    ('rl_login',    '/accounts/login/',       10,  60,  False),  # страница входа
    ('rl_reg',      '/api/register_public/',   5, 300,  True),   # регистрация
    ('rl_api',      '/api/',                 300,  60,  True),   # весь API
]


def _get_ip(request):
    """Возвращает реальный IP-адрес клиента.
    Учитывает цепочку прокси через заголовок X-Forwarded-For.
    """
    # Заголовок X-Forwarded-For содержит список IP: клиент, прокси1, прокси2, ...
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        # Берём первый IP — он соответствует исходному клиенту
        return x_forwarded.split(',')[0].strip()
    # Нет прокси — берём прямой IP (REMOTE_ADDR), дефолт '0.0.0.0'
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


class RateLimitMiddleware:
    """Middleware для ограничения частоты запросов (rate limiting)."""

    def __init__(self, get_response):
        # get_response — следующий обработчик в цепочке middleware/view
        self.get_response = get_response

    def __call__(self, request):
        # Получаем путь текущего запроса
        path = request.path

        # Перебираем все правила ограничений
        for prefix, url_prefix, max_req, window, is_api in _RATE_RULES:
            # Проверяем, подходит ли URL под текущее правило
            if not path.startswith(url_prefix):
                continue  # Правило не подходит — переходим к следующему

            # Получаем IP клиента
            ip = _get_ip(request)
            # Формируем ключ кэша: prefix:ip
            key = f'{prefix}:{ip}'
            # Текущее время в секундах (unix timestamp)
            now = int(time.time())
            # Ключ окна: делим время на размер окна, получаем номер текущего окна
            # Все запросы в одном окне накапливают один счётчик
            window_key = f'{key}:{now // window}'

            # Читаем текущий счётчик из кэша (0 если ключа нет)
            count = cache.get(window_key, 0)
            if count >= max_req:
                # Лимит превышен — логируем предупреждение
                logger.warning(
                    'rate_limit: ip=%s path=%s count=%d limit=%d',
                    ip, path, count, max_req,
                )
                if is_api:
                    # Для API-запросов возвращаем JSON с кодом 429
                    return JsonResponse(
                        {'error': 'Слишком много запросов. Попробуйте позже.'},
                        status=429,
                    )
                # Для HTML-страниц возвращаем простой HTTP 429
                from django.http import HttpResponse
                return HttpResponse(
                    'Слишком много попыток. Подождите и попробуйте снова.',
                    status=429,
                    content_type='text/plain; charset=utf-8',
                )

            # Увеличиваем счётчик на 1 и обновляем TTL = размер окна
            cache.set(window_key, count + 1, timeout=window)
            break  # применяем только первое совпавшее правило

        # Передаём запрос следующему обработчику (middleware или view)
        return self.get_response(request)
