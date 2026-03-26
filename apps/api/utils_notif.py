"""
Вспомогательные функции для создания уведомлений.

Использование:
    from apps.api.utils_notif import create_notification
    create_notification(user, 'task', 'Новая задача', message='...', link='/plan/')
"""


def create_notification(user, type, title, message='', link=''):
    """Создать уведомление для пользователя.

    Args:
        user: экземпляр auth.User
        type: тип уведомления (info, warning, success, task, overdue, sandbox)
        title: заголовок
        message: текст сообщения (необязательно)
        link: ссылка для перехода (необязательно)

    Returns:
        Notification instance
    """
    from apps.works.models import Notification
    return Notification.objects.create(
        user=user, type=type, title=title, message=message, link=link,
    )
