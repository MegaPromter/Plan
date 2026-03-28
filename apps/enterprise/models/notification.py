"""
Уведомления модуля «Управление предприятием».

Типы: запросы на перераспределение, смена фаз, подтверждение приоритетов.
Отдельная модель от works.Notification — расширенная, с GenericFK.
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class EnterpriseNotification(models.Model):
    """Уведомление (колокольчик в шапке)."""

    # Типы уведомлений
    TYPE_REALLOCATION_REQUEST = 'reallocation_request'
    TYPE_REALLOCATION_RESULT = 'reallocation_result'
    TYPE_PHASE_CHANGE = 'phase_change'
    TYPE_PRIORITY_CONFIRM = 'priority_confirm'

    TYPE_CHOICES = [
        (TYPE_REALLOCATION_REQUEST, 'Запрос на перераспределение'),
        (TYPE_REALLOCATION_RESULT, 'Результат согласования'),
        (TYPE_PHASE_CHANGE, 'Смена фазы'),
        (TYPE_PRIORITY_CONFIRM, 'Подтверждение приоритетов'),
    ]

    recipient = models.ForeignKey(
        'employees.Employee', on_delete=models.CASCADE,
        related_name='enterprise_notifications',
        verbose_name='Получатель',
    )
    notification_type = models.CharField(
        'Тип', max_length=30, choices=TYPE_CHOICES,
    )
    title = models.CharField('Заголовок', max_length=200)
    message = models.TextField('Текст', blank=True)

    # Generic FK — ссылка на любой объект (проект, сквозной график и т.д.)
    related_content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Тип объекта',
    )
    related_object_id = models.PositiveIntegerField(
        'ID объекта', null=True, blank=True,
    )
    related_object = GenericForeignKey('related_content_type', 'related_object_id')

    is_read = models.BooleanField('Прочитано', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        db_table = 'ent_notification'
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['recipient', 'is_read', 'created_at'],
                name='ent_notif_recipient_idx',
            ),
        ]

    def __str__(self):
        return f'{self.recipient} — {self.title}'
