"""
Сигналы приложения employees.

Синхронизирует Work.executor_name_raw с Employee.full_name
при изменении имени сотрудника (last_name / first_name / patronymic).
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='employees.Employee')
def sync_executor_name_raw(sender, instance, created, **kwargs):
    """
    После сохранения Employee обновляем Work.executor_name_raw
    для всех работ, где executor = этот сотрудник.

    Используем update() — без вызова save() на каждой работе,
    что экономит запросы и не переписывает updated_at.
    """
    if created:
        return  # При создании executor_name_raw ещё не заполнен

    try:
        from apps.works.models import Work
        new_name = instance.full_name
        updated = Work.objects.filter(executor=instance).update(
            executor_name_raw=new_name,
        )
        if updated:
            logger.info(
                'sync_executor_name_raw: employee=%s updated %d work(s)',
                instance.pk, updated,
            )
    except Exception as e:
        logger.error('sync_executor_name_raw error: %s', e, exc_info=True)
