"""
Сигналы приложения employees.

Авто-делегирование при уходе в отпуск:
- post_save(Vacation): создаёт/обновляет RoleDelegation если auto_delegate_enabled
- post_delete(Vacation): удаляет авто-делегирование, привязанное к отпуску

Напоминание за 3 дня до отпуска:
- post_save(Vacation): если нет авто-делегирования и нет активного делегирования →
  создаёт EnterpriseNotification с напоминанием.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)

# Количество дней до отпуска для напоминания
REMINDER_DAYS = 3


def _resolve_delegation_scope(employee):
    """Определяет (scope_type, scope_value) по роли сотрудника.

    Возвращает tuple или None если scope не определяется.
    """
    role = employee.role
    if role in ("ntc_head", "ntc_deputy"):
        if employee.ntc_center:
            return ("center", employee.ntc_center.code)
    elif role in ("dept_head", "dept_deputy"):
        if employee.department:
            return ("dept", employee.department.code)
    elif role == "sector_head":
        if employee.sector:
            return ("sector", employee.sector.code)
    elif role in ("chief_designer", "deputy_gd_econ", "admin"):
        # Эти роли не привязаны к конкретному подразделению стандартно;
        # делегируем на уровне отдела если есть
        if employee.department:
            return ("dept", employee.department.code)
    return None


def _create_auto_delegation(vacation, employee):
    """Создаёт авто-делегирование для отпуска, если настроено."""
    from apps.employees.models import RoleDelegation

    col = employee.col_settings or {}
    if not col.get("auto_delegate_enabled"):
        return None

    delegate_id = col.get("auto_delegate_employee_id")
    if not delegate_id:
        return None

    # Не создаём дубликат
    existing = RoleDelegation.objects.filter(source_vacation=vacation).first()
    if existing:
        # Обновляем valid_until если даты отпуска изменились
        new_until = timezone.make_aware(
            timezone.datetime.combine(vacation.date_end, timezone.datetime.max.time())
        )
        if existing.valid_until != new_until:
            existing.valid_until = new_until
            existing.save(update_fields=["valid_until"])
            logger.info(
                "Авто-делегирование #%s обновлено: valid_until=%s",
                existing.pk,
                new_until,
            )
        return existing

    scope = _resolve_delegation_scope(employee)
    if not scope:
        logger.warning(
            "Не удалось определить scope для авто-делегирования: employee=%s role=%s",
            employee.pk,
            employee.role,
        )
        return None

    from apps.employees.models import Employee

    try:
        delegate = Employee.objects.get(pk=delegate_id)
    except Employee.DoesNotExist:
        logger.warning(
            "Заместитель id=%s не найден для авто-делегирования", delegate_id
        )
        return None

    if delegate.pk == employee.pk:
        return None

    valid_until = timezone.make_aware(
        timezone.datetime.combine(vacation.date_end, timezone.datetime.max.time())
    )

    rd = RoleDelegation.objects.create(
        delegator=employee,
        delegate=delegate,
        scope_type=scope[0],
        scope_value=scope[1],
        can_write=True,
        valid_until=valid_until,
        source_vacation=vacation,
    )

    # Инвалидируем кэш делегирований получателя
    from django.core.cache import cache

    cache.delete(f"delegations:{delegate.pk}")

    logger.info(
        "Авто-делегирование #%s создано: %s → %s [%s:%s] до %s",
        rd.pk,
        employee.short_name,
        delegate.short_name,
        scope[0],
        scope[1],
        valid_until,
    )
    return rd


def _maybe_send_reminder(vacation, employee):
    """Отправляет напоминание о делегировании за 3 дня до отпуска."""
    from apps.enterprise.models.notification import EnterpriseNotification

    # Не напоминаем если авто-делегирование включено
    col = employee.col_settings or {}
    if col.get("auto_delegate_enabled"):
        return

    # Не напоминаем рядовым (им нечего делегировать)
    if not employee.is_writer:
        return

    today = timezone.now().date()
    days_until = (vacation.date_start - today).days

    if days_until < 0 or days_until > REMINDER_DAYS:
        return

    # Проверяем нет ли уже активного делегирования от этого сотрудника
    from apps.employees.models import RoleDelegation

    has_active = RoleDelegation.objects.filter(
        delegator=employee,
        valid_until__gt=timezone.now(),
    ).exists()
    if has_active:
        return

    # Проверяем нет ли уже напоминания для этого отпуска
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(vacation)
    already_sent = EnterpriseNotification.objects.filter(
        recipient=employee,
        notification_type=EnterpriseNotification.TYPE_DELEGATION_REMINDER,
        related_content_type=ct,
        related_object_id=vacation.pk,
    ).exists()
    if already_sent:
        return

    if days_until == 0:
        text = "Сегодня начинается отпуск."
    elif days_until == 1:
        text = "Завтра начинается отпуск."
    else:
        text = f"Через {days_until} дн. начинается отпуск."

    EnterpriseNotification.objects.create(
        recipient=employee,
        notification_type=EnterpriseNotification.TYPE_DELEGATION_REMINDER,
        title=f"{text} Настройте делегирование прав.",
        message=(
            f"Отпуск: {vacation.date_start} — {vacation.date_end}. "
            "Перейдите в раздел «Делегирование» для настройки."
        ),
        related_content_type=ct,
        related_object_id=vacation.pk,
    )
    logger.info(
        "Напоминание о делегировании создано для %s (отпуск #%s)",
        employee.short_name,
        vacation.pk,
    )


@receiver(post_save, sender="employees.Vacation")
def on_vacation_save(sender, instance, **kwargs):
    """При создании/обновлении отпуска: авто-делегирование + напоминание."""
    vacation = instance
    employee = vacation.employee

    # Авто-делегирование
    _create_auto_delegation(vacation, employee)

    # Напоминание
    _maybe_send_reminder(vacation, employee)


@receiver(post_delete, sender="employees.Vacation")
def on_vacation_delete(sender, instance, **kwargs):
    """При удалении отпуска: удаляем привязанное авто-делегирование."""
    from apps.employees.models import RoleDelegation

    deleted_count, _ = RoleDelegation.objects.filter(source_vacation=instance).delete()
    if deleted_count:
        logger.info(
            "Удалено %s авто-делегирований при удалении отпуска #%s",
            deleted_count,
            instance.pk,
        )
        # Инвалидируем кэш
        from django.core.cache import cache

        # Не знаем точно delegate, чистим по delegator
        cache.delete(f"delegations:{instance.employee.pk}")
