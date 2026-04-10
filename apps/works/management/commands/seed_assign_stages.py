"""
Management command: назначает коды строк и наряд-заказы для всех этапов,
а также привязывает все работы к этапам (равномерно).

Использование: python manage.py seed_assign_stages
Идемпотентен — безопасно запускать повторно.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.works.models import PPStage, Project, Work


class Command(BaseCommand):
    help = "Назначает row_code/work_order этапам и привязывает работы к этапам"

    def handle(self, *args, **options):
        projects = list(Project.objects.all().order_by("name_short"))

        with transaction.atomic():
            for proj in projects:
                stages = list(
                    PPStage.objects.filter(project=proj).order_by("order", "id")
                )
                if not stages:
                    self.stdout.write(f"{proj.name_short}: нет этапов, пропуск")
                    continue

                # 1. Назначаем row_code и work_order пустым этапам
                prefix = proj.name_short or proj.code or f"П{proj.id}"
                updated_stages = 0
                for s in stages:
                    changed = False
                    if not s.row_code:
                        s.row_code = f"{prefix}.{s.stage_number}"
                        changed = True
                    if not s.work_order:
                        s.work_order = f"НЗ-{prefix}.{s.stage_number}"
                        changed = True
                    if changed:
                        s.save(update_fields=["row_code", "work_order"])
                        updated_stages += 1

                # 2. Привязываем работы без этапа к этапам (равномерно)
                works_no_stage = list(
                    Work.objects.filter(
                        project=proj, pp_stage__isnull=True, show_in_pp=True
                    ).values_list("id", flat=True)
                )
                if not works_no_stage:
                    self.stdout.write(
                        f"{proj.name_short}: обновлено {updated_stages} этапов, "
                        f"все работы уже привязаны"
                    )
                    continue

                # Распределяем работы по этапам равномерно
                assigned = 0
                for i, work_id in enumerate(works_no_stage):
                    stage = stages[i % len(stages)]
                    Work.objects.filter(id=work_id).update(
                        pp_stage=stage,
                        stage_num=stage.stage_number,
                    )
                    assigned += 1

                self.stdout.write(
                    f"{proj.name_short}: обновлено {updated_stages} этапов, "
                    f"привязано {assigned} работ к {len(stages)} этапам"
                )

        self.stdout.write(self.style.SUCCESS("Готово"))
