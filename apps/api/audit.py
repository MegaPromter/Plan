"""
Утилиты для аудит-логирования действий пользователей.
Используется в API-вьюхах для записи в AuditLog.
"""
# Стандартный модуль логирования Python
import logging

# Создаём логгер для данного модуля (имя = полный путь модуля)
logger = logging.getLogger(__name__)


from apps.api.utils import get_client_ip as _get_ip


def log_action(request, action, object_id=None, object_repr='', details=None):
    """
    Записывает действие в AuditLog.
    Использует lazy-import, чтобы не создавать циклических зависимостей.
    """
    try:
        # Ленивый импорт модели — выполняется только при вызове функции,
        # что позволяет избежать циклических импортов на уровне модуля
        from apps.works.models import AuditLog
        # Создаём запись в таблице аудита
        AuditLog.objects.create(
            # Пользователь: None если не авторизован (на случай анонимных действий)
            user=request.user if request.user.is_authenticated else None,
            # Код действия (например, 'task_create', 'pp_sync' и т.д.)
            action=action,
            # ID объекта, над которым совершено действие (может быть None)
            object_id=object_id,
            # Строковое представление объекта (обрезаем до 500 символов)
            object_repr=object_repr[:500],
            # Дополнительные данные в виде dict (если не переданы — пустой dict)
            details=details or {},
            # IP-адрес клиента (получаем через вспомогательную функцию)
            ip_address=_get_ip(request),
        )
    except Exception as e:
        # Не ломаем основной запрос из-за ошибки в аудите
        # Логируем ошибку с трейсбеком, но не пробрасываем исключение дальше
        logger.error('audit log error: %s', e, exc_info=True)
