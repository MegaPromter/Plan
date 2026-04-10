"""
Management command: создаёт отчёты (WorkReport) для 75% работ за февраль-март 2026.
Использование: python manage.py seed_reports
Идемпотентен: удаляет старые seed-отчёты перед созданием.
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.works.models import Work, WorkReport

_SEED_TAG = "SEED_WORKLOAD"  # совпадает с тегом из seed_workload (work_designation)
_REPORT_TAG = "SEED_REPORT"  # тег в doc_designation для идентификации seed-отчётов

DOC_NAMES = [
    "Чертёж общего вида",
    "Сборочный чертёж",
    "Спецификация",
    "Схема электрическая",
    "Расчёт прочности",
    "Расчёт теплового режима",
    "Ведомость покупных",
    "Программа испытаний",
    "Технические условия",
    "Пояснительная записка",
    "Расчёт надёжности",
    "Монтажный чертёж",
    "Габаритный чертёж",
    "Ведомость согласования",
    "Акт проверки",
    "Протокол испытаний",
    "Ведомость комплекта",
    "Паспорт изделия",
    "Формуляр",
]

DOC_TYPES = ["design", "tech", "report", "program", "other"]
DOC_CLASSES = ["original", "copy", "draft"]


class Command(BaseCommand):
    help = "Создаёт отчёты для 75% работ за февраль-март 2026"

    def handle(self, *args, **options):
        random.seed(42)

        # Работы за февраль-март с тегом seed
        works = list(
            Work.objects.filter(
                work_designation=_SEED_TAG,
                date_start__year=2026,
                date_start__month__in=[2, 3],
            ).select_related("project", "executor")
        )
        if not works:
            self.stderr.write("Нет seed-работ за февраль-март 2026")
            return

        self.stdout.write(f"Найдено {len(works)} работ за фев-март")

        # Удаляем старые seed-отчёты
        deleted, _ = WorkReport.objects.filter(doc_designation=_REPORT_TAG).delete()
        if deleted:
            self.stdout.write(f"Удалено старых seed-отчётов: {deleted}")

        # 75% работ получают отчёт
        random.shuffle(works)
        count_with_report = int(len(works) * 0.75)
        works_with_report = works[:count_with_report]

        reports_to_create = []
        for w in works_with_report:
            # Дата выпуска: от date_start до date_end (или +10 дней)
            d_start = w.date_start
            d_end = w.date_end or (d_start + timedelta(days=10))
            delta = (d_end - d_start).days
            if delta < 1:
                delta = 5
            date_accepted = d_start + timedelta(days=random.randint(1, max(1, delta)))

            sheets = random.randint(1, 30)
            norm_val = round(random.uniform(0.5, 8.0), 2)
            coeff_val = round(random.uniform(0.8, 1.5), 3)
            bvd = round(sheets * float(norm_val) * float(coeff_val), 2)

            report = WorkReport(
                work=w,
                doc_name=random.choice(DOC_NAMES),
                doc_designation=_REPORT_TAG,
                doc_number=f"ИИ-{w.work_num}" if w.work_num else "",
                date_accepted=date_accepted,
                doc_type=random.choice(DOC_TYPES),
                doc_class=random.choice(DOC_CLASSES),
                sheets_a4=sheets,
                norm=norm_val,
                coeff=coeff_val,
                bvd_hours=bvd,
            )
            reports_to_create.append(report)

        with transaction.atomic():
            WorkReport.objects.bulk_create(reports_to_create, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f"Создано {len(reports_to_create)} отчётов "
                f"({count_with_report} из {len(works)} работ = 75%)"
            )
        )
