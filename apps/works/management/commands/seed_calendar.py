"""
Management command: засевает справочные данные — производственный календарь, праздники, типы задач.
Использование: python manage.py seed_calendar
Идемпотентен (get_or_create) — безопасно запускать при каждом деплое.
"""
from django.core.management.base import BaseCommand
from apps.works.models import WorkCalendar, Holiday, Directory
from datetime import date


# Нормы рабочих часов на 2026 год (Россия, 40-часовая неделя)
CALENDAR_2026 = [
    (2026, 1, 120),
    (2026, 2, 152),
    (2026, 3, 168),
    (2026, 4, 176),
    (2026, 5, 143),
    (2026, 6, 167),
    (2026, 7, 184),
    (2026, 8, 168),
    (2026, 9, 176),
    (2026, 10, 176),
    (2026, 11, 159),
    (2026, 12, 183),
]

# Нерабочие праздничные дни 2026 (ст. 112 ТК РФ + переносы)
HOLIDAYS_2026 = [
    (date(2026, 1, 1), 'Новогодние каникулы'),
    (date(2026, 1, 2), 'Новогодние каникулы'),
    (date(2026, 1, 5), 'Новогодние каникулы'),
    (date(2026, 1, 6), 'Новогодние каникулы'),
    (date(2026, 1, 7), 'Рождество Христово'),
    (date(2026, 1, 8), 'Новогодние каникулы'),
    (date(2026, 2, 23), 'День защитника Отечества'),
    (date(2026, 3, 9), 'Международный женский день (перенос с 8 марта)'),
    (date(2026, 5, 1), 'Праздник Весны и Труда'),
    (date(2026, 5, 4), 'Перенос выходного'),
    (date(2026, 5, 11), 'День Победы (перенос с 9 мая)'),
    (date(2026, 6, 12), 'День России'),
    (date(2026, 11, 4), 'День народного единства'),
    (date(2026, 12, 31), 'Новогодние каникулы'),
]


# Типы задач (справочник Directory, dir_type='task_type')
TASK_TYPES = [
    'Выпуск нового документа',
    'Корректировка документа',
    'Разработка',
    'Сопровождение (ОКАН)',
    'Проверка расчётной записки',
]


class Command(BaseCommand):
    help = 'Засевает справочные данные: календарь, праздники, типы задач'

    def handle(self, *args, **options):
        # Типы задач
        created_tt = 0
        for val in TASK_TYPES:
            _, is_new = Directory.objects.get_or_create(
                dir_type='task_type', value=val,
            )
            if is_new:
                created_tt += 1
        self.stdout.write(f'TaskTypes: {created_tt} создано, {len(TASK_TYPES) - created_tt} уже были')

        # Производственный календарь
        created_cal = 0
        for year, month, hours in CALENDAR_2026:
            _, is_new = WorkCalendar.objects.get_or_create(
                year=year, month=month,
                defaults={'hours_norm': hours},
            )
            if is_new:
                created_cal += 1
        self.stdout.write(f'WorkCalendar: {created_cal} создано, {len(CALENDAR_2026) - created_cal} уже были')

        # Праздничные дни
        created_hol = 0
        for d, name in HOLIDAYS_2026:
            _, is_new = Holiday.objects.get_or_create(
                date=d,
                defaults={'name': name},
            )
            if is_new:
                created_hol += 1
        self.stdout.write(f'Holiday: {created_hol} создано, {len(HOLIDAYS_2026) - created_hol} уже были')

        self.stdout.write(self.style.SUCCESS('Готово!'))
