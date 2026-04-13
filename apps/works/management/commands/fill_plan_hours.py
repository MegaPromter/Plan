"""
Заполняет plan_hours для всех задач СП (show_in_plan=True).

Для каждой задачи определяет месяцы между date_start и date_end,
считает рабочие дни (пн-пт, минус holidays) в каждом месяце,
и распределяет общую сумму часов пропорционально рабочим дням.

Если plan_hours уже есть — берёт total из суммы существующих значений.
Если пуст — total = рабочие_дни × 8.

Использование:
  python manage.py fill_plan_hours --dry-run   # только статистика
  python manage.py fill_plan_hours              # выполнить
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.works.models import Holiday, Work


def _load_holidays():
    """Множество дат-праздников из Holiday."""
    return set(Holiday.objects.values_list("date", flat=True))


def _work_days_in_range(start, end, holidays):
    """Кол-во рабочих дней (пн-пт, минус holidays) от start до end включительно."""
    count = 0
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in holidays:
            count += 1
        d += timedelta(days=1)
    return count


def _months_between(start, end):
    """Генерирует (year, month) от start до end включительно."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def _month_range_clamp(year, month, task_start, task_end):
    """Границы задачи внутри конкретного месяца."""
    from calendar import monthrange

    _, last_day = monthrange(year, month)
    m_start = date(year, month, 1)
    m_end = date(year, month, last_day)
    return max(m_start, task_start), min(m_end, task_end)


class Command(BaseCommand):
    help = "Заполняет plan_hours для задач СП пропорционально рабочим дням"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать статистику, не менять данные",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        holidays = _load_holidays()

        tasks = list(
            Work.objects.filter(show_in_plan=True)
            .filter(date_start__isnull=False, date_end__isnull=False)
            .only("id", "plan_hours", "date_start", "date_end")
        )

        self.stdout.write(f"Всего задач СП с датами: {len(tasks)}")

        updated = 0
        skipped_single = 0
        skipped_no_days = 0

        for w in tasks:
            months = list(_months_between(w.date_start, w.date_end))

            # Если задача в одном месяце и plan_hours уже есть — пропускаем
            if len(months) == 1:
                ph = w.plan_hours or {}
                key = f"{months[0][0]}-{months[0][1]:02d}"
                if ph.get(key):
                    skipped_single += 1
                    continue

            # Считаем рабочие дни в каждом месяце
            month_days = {}
            for y, m in months:
                cstart, cend = _month_range_clamp(y, m, w.date_start, w.date_end)
                wd = _work_days_in_range(cstart, cend, holidays)
                month_days[(y, m)] = wd

            total_work_days = sum(month_days.values())
            if total_work_days == 0:
                skipped_no_days += 1
                continue

            # Определяем total часов
            old_ph = w.plan_hours or {}
            if old_ph:
                total_hours = sum(float(v) for v in old_ph.values() if v)
            else:
                total_hours = total_work_days * 8.0

            if total_hours <= 0:
                skipped_no_days += 1
                continue

            # Распределяем пропорционально
            new_ph = {}
            distributed = 0.0
            sorted_months = sorted(month_days.keys())
            for i, (y, m) in enumerate(sorted_months):
                key = f"{y}-{m:02d}"
                wd = month_days[(y, m)]
                if i == len(sorted_months) - 1:
                    # Последний месяц — остаток (чтобы не терять на округлении)
                    hours = round(total_hours - distributed, 1)
                else:
                    hours = round(total_hours * wd / total_work_days, 1)
                    distributed += hours
                # Минимум 1 час, если в месяце есть рабочие дни
                if wd > 0 and hours < 1.0:
                    hours = 1.0
                # Не записываем месяцы без рабочих дней (праздники)
                if hours > 0:
                    new_ph[key] = hours

            w.plan_hours = new_ph
            if not dry_run:
                w.save(update_fields=["plan_hours"])
            updated += 1

        mode = "DRY-RUN" if dry_run else "DONE"
        self.stdout.write(
            f"[{mode}] Обновлено: {updated}, "
            f"Одномесячные (ок): {skipped_single}, "
            f"Без рабочих дней: {skipped_no_days}"
        )
