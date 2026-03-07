"""
Утилиты для аудит-логирования действий пользователей.
Используется в API-вьюхах для записи в AuditLog.
"""
import logging

logger = logging.getLogger(__name__)


def _get_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_action(request, action, object_id=None, object_repr='', details=None):
    """
    Записывает действие в AuditLog.
    Использует lazy-import, чтобы не создавать циклических зависимостей.
    """
    try:
        from apps.works.models import AuditLog
        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action=action,
            object_id=object_id,
            object_repr=object_repr[:500],
            details=details or {},
            ip_address=_get_ip(request),
        )
    except Exception as e:
        # Не ломаем основной запрос из-за ошибки в аудите
        logger.error('audit log error: %s', e, exc_info=True)
