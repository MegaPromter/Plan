"""
Management command: засевает справочник НТЦ-центров.
Использование: python manage.py seed_centers
Идемпотентен (get_or_create) — безопасно запускать при каждом деплое.
"""

from django.core.management.base import BaseCommand

from apps.employees.models import NTCCenter

# Базовый набор центров для первого развёртывания.
# Миграция 0007 дополнительно создаёт «НТЦ-16Ц».
DEFAULT_CENTERS = [
    {"code": "Центр 1", "name": ""},
    {"code": "Центр 2", "name": ""},
    {"code": "Центр 3", "name": ""},
    {"code": "Центр 4", "name": ""},
]


class Command(BaseCommand):
    help = "Создаёт базовые НТЦ-центры (Центр 1..4), если их ещё нет."

    def handle(self, *args, **options):
        created = 0
        for item in DEFAULT_CENTERS:
            _, was_created = NTCCenter.objects.get_or_create(
                code=item["code"],
                defaults={"name": item["name"]},
            )
            if was_created:
                created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"seed_centers: готово. Создано новых: {created}, "
                f"всего в справочнике: {NTCCenter.objects.count()}"
            )
        )
