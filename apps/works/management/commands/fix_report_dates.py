"""
Management command: исправление дат создания отчётов (WorkReport.created_at).

Проблема: все отчёты засеяны одномоментно и имеют created_at в апреле 2026.
Решение: ставим created_at = date_end работы + случайный сдвиг 0-5 дней,
чтобы имитировать реалистичное заполнение.

created_at — DateTimeField(auto_now_add=True), поэтому обычный save()
не обновит это поле. Используем queryset.filter(pk=...).update() —
Django ORM при .update() не вызывает auto_now_add логику.
"""

import random
from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.works.models import WorkReport


class Command(BaseCommand):
    help = "Исправляет created_at отчётов: ставит дату близкую к date_end работы"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать что будет изменено, без записи в БД",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Seed для генератора случайных чисел (по умолчанию 42)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        rng = random.Random(options["seed"])

        reports = WorkReport.objects.select_related("work").all()
        total = reports.count()

        updated = 0
        skipped = 0
        # Статистика по месяцам: год-месяц → количество
        month_stats = defaultdict(int)

        for report in reports:
            work = report.work
            # Берём дату окончания работы: date_end или deadline
            base_date = work.date_end or work.deadline

            if not base_date:
                skipped += 1
                continue

            # Случайный сдвиг 0-5 дней после окончания работы
            offset_days = rng.randint(0, 5)
            new_date = base_date + timedelta(days=offset_days)

            # Преобразуем date → datetime (полночь, с учётом timezone)
            new_datetime = timezone.make_aware(
                timezone.datetime(
                    new_date.year,
                    new_date.month,
                    new_date.day,
                    rng.randint(9, 17),  # случайный час 9-17
                    rng.randint(0, 59),
                ),  # случайная минута
            )

            month_key = f"{new_date.year}-{new_date.month:02d}"
            month_stats[month_key] += 1

            if not dry_run:
                # .update() обходит auto_now_add
                WorkReport.objects.filter(pk=report.pk).update(created_at=new_datetime)

            updated += 1

        # Вывод результатов
        mode = "DRY RUN" if dry_run else "ВЫПОЛНЕНО"
        self.stdout.write(f"\n{'=' * 50}")
        self.stdout.write(f"  {mode}")
        self.stdout.write(f"{'=' * 50}")
        self.stdout.write(f"  Всего отчётов:    {total}")
        self.stdout.write(f"  Обновлено:        {updated}")
        self.stdout.write(f"  Пропущено:        {skipped} (нет date_end/deadline)")

        if month_stats:
            self.stdout.write("\n  Распределение по месяцам:")
            for month in sorted(month_stats):
                self.stdout.write(f"    {month}: {month_stats[month]}")

        self.stdout.write(f"{'=' * 50}\n")
