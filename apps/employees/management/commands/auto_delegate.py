"""
Management command: авто-делегирование и напоминания.

Ежедневный cron: проверяет сотрудников с auto_delegate_enabled,
создаёт делегирования для текущих отпусков и напоминания за 3 дня.

Использование:
    python manage.py auto_delegate
    python manage.py auto_delegate --dry-run
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.employees.models import Employee, Vacation
from apps.employees.signals import (
    REMINDER_DAYS,
    _create_auto_delegation,
    _maybe_send_reminder,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Создаёт авто-делегирования для текущих отпусков и напоминания"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать что будет сделано, без изменений",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        today = timezone.now().date()
        # Дата для проверки напоминаний: отпуска начинающиеся в ближайшие N дней
        reminder_horizon = today + timezone.timedelta(days=REMINDER_DAYS)

        # Все сотрудники-писатели (потенциальные делегаторы)
        writers = Employee.objects.filter(
            user__is_active=True,
        ).exclude(role=Employee.ROLE_USER)

        created_count = 0
        reminder_count = 0

        for emp in writers:
            col = emp.col_settings or {}

            # 1. Авто-делегирование: текущие отпуска
            if col.get("auto_delegate_enabled") and col.get(
                "auto_delegate_employee_id"
            ):
                active_vacations = Vacation.objects.filter(
                    employee=emp,
                    date_start__lte=today,
                    date_end__gte=today,
                )
                for vac in active_vacations:
                    if dry_run:
                        self.stdout.write(
                            f"[DRY-RUN] Авто-делегирование: {emp.short_name} "
                            f"(отпуск {vac.date_start}–{vac.date_end})"
                        )
                    else:
                        rd = _create_auto_delegation(vac, emp)
                        if rd:
                            created_count += 1

            # 2. Напоминания: отпуска в ближайшие N дней
            upcoming = Vacation.objects.filter(
                employee=emp,
                date_start__gt=today,
                date_start__lte=reminder_horizon,
            )
            for vac in upcoming:
                if dry_run:
                    days = (vac.date_start - today).days
                    self.stdout.write(
                        f"[DRY-RUN] Напоминание: {emp.short_name} "
                        f"(отпуск через {days} дн.)"
                    )
                else:
                    _maybe_send_reminder(vac, emp)
                    reminder_count += 1

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run завершён"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Готово: {created_count} делегирований, "
                    f"{reminder_count} напоминаний обработано"
                )
            )
