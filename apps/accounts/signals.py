"""Сигналы аутентификации — логирование входов/выходов/неудачных попыток."""

import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _client_ip(request):
    """Извлечь IP клиента из запроса (с учётом прокси)."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "?")


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    logger.info("LOGIN OK: user='%s' ip=%s", user.username, _client_ip(request))


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    name = user.username if user else "?"
    logger.info("LOGOUT: user='%s' ip=%s", name, _client_ip(request))


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    ip = _client_ip(request) if request else "?"
    username = credentials.get("username", "?")
    logger.warning("LOGIN FAIL: user='%s' ip=%s", username, ip)
