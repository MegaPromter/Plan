"""
Сигналы приложения employees.

Синхронизирует Work.executor_name_raw с Employee.full_name
при изменении имени сотрудника (last_name / first_name / patronymic).
"""
# Стандартный модуль логирования Python
import logging

# post_save — сигнал, отправляемый после сохранения экземпляра модели в БД
from django.db.models.signals import post_save
# receiver — декоратор для подключения функции-обработчика к сигналу
from django.dispatch import receiver

# Логгер для данного модуля (имя = 'apps.employees.signals')
logger = logging.getLogger(__name__)


# Декоратор подключает обработчик к сигналу post_save модели Employee
# Используем строковую ссылку 'employees.Employee' во избежание циклического импорта
@receiver(post_save, sender='employees.Employee')
def sync_executor_name_raw(sender, instance, created, **kwargs):
    """
    После сохранения Employee обновляем Work.executor_name_raw
    для всех работ, где executor = этот сотрудник.

    Используем update() — без вызова save() на каждой работе,
    что экономит запросы и не переписывает updated_at.
    """
    # При создании нового сотрудника executor_name_raw ещё не заполнен ни в одной работе,
    # поэтому синхронизация не нужна
    if created:
        return  # При создании executor_name_raw ещё не заполнен

    try:
        # Импортируем Work здесь (не на уровне модуля) во избежание циклического импорта:
        # employees.signals → works.models → employees.models → employees.signals
        from apps.works.models import Work
        # Получаем актуальное полное имя сотрудника (может измениться после сохранения)
        new_name = instance.full_name
        # Массовое обновление: устанавливаем executor_name_raw для всех работ,
        # где FK executor указывает на данного сотрудника
        # update() не вызывает save() и не обновляет Work.updated_at — это намеренно
        updated = Work.objects.filter(executor=instance).update(
            executor_name_raw=new_name,
        )
        # Логируем только если были реально обновлены записи
        if updated:
            logger.info(
                'sync_executor_name_raw: employee=%s updated %d work(s)',
                instance.pk, updated,
            )
    except Exception as e:
        # Логируем ошибку с трейсбэком, но не пробрасываем исключение —
        # сбой синхронизации не должен прерывать сохранение сотрудника
        logger.error('sync_executor_name_raw error: %s', e, exc_info=True)
