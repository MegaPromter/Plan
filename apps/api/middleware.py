"""
Rate-limiting middleware для защиты API от брутфорса.

Ограничения:
- /accounts/login/       : 10 попыток / 60 сек с одного IP
- /api/register_public/  : 5 попыток / 300 сек с одного IP
- /api/                  : 300 запросов / 60 сек с одного IP (общий лимит)
"""
import time
import logging
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

# (prefix, max_requests, window_seconds, is_api)
_RATE_RULES = [
    ('rl_login',    '/accounts/login/',       10,  60,  False),
    ('rl_reg',      '/api/register_public/',   5, 300,  True),
    ('rl_api',      '/api/',                 300,  60,  True),
]


def _get_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        for prefix, url_prefix, max_req, window, is_api in _RATE_RULES:
            if not path.startswith(url_prefix):
                continue

            ip = _get_ip(request)
            key = f'{prefix}:{ip}'
            now = int(time.time())
            window_key = f'{key}:{now // window}'

            count = cache.get(window_key, 0)
            if count >= max_req:
                logger.warning(
                    'rate_limit: ip=%s path=%s count=%d limit=%d',
                    ip, path, count, max_req,
                )
                if is_api:
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

            cache.set(window_key, count + 1, timeout=window)
            break  # применяем только первое совпавшее правило

        return self.get_response(request)
