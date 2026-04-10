"""
Миграция: объединение Work + PPWork + TaskWork в одну таблицу.

1. Добавляем в Work все поля из PPWork и TaskWork.
2. Переносим данные (RunPython).
3. Удаляем таблицы PPWork, TaskWork, WorkType.
4. Удаляем поле source_type и work_type из Work.
"""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def migrate_data_forward(apps, schema_editor):
    """Перенос данных из PPWork/TaskWork в Work."""
    PPWork = apps.get_model("works", "PPWork")
    TaskWork = apps.get_model("works", "TaskWork")

    # Перенос из PPWork → Work
    pp_works = PPWork.objects.select_related("work").all()
    for pp in pp_works:
        w = pp.work
        w.show_in_pp = True
        w.task_type = pp.task_type or ""
        w.pp_project_id = pp.pp_project_id
        w.row_code = pp.row_code or ""
        w.work_order = pp.work_order or ""
        w.stage_num = pp.stage_num or ""
        w.milestone_num = pp.milestone_num or ""
        w.work_num = pp.work_num or ""
        w.work_designation = pp.work_designation or ""
        w.sheets_a4 = pp.sheets_a4
        w.norm = pp.norm
        w.coeff = pp.coeff
        w.total_2d = pp.total_2d
        w.total_3d = pp.total_3d
        w.labor = pp.labor
        w.sector_head_name = pp.sector_head_name or ""
        w.save()

    # Перенос из TaskWork → Work
    task_works = TaskWork.objects.select_related("work").all()
    for tw in task_works:
        w = tw.work
        w.show_in_plan = True
        w.stage = tw.stage or ""
        w.justification = tw.justification or ""
        w.executors_list = (
            tw.executors_list if isinstance(tw.executors_list, list) else []
        )
        w.actions = tw.actions if isinstance(tw.actions, dict) else {}
        # task_type из WorkType FK (если есть) — переносим имя типа
        if w.work_type_id:
            try:
                WorkType = apps.get_model("works", "WorkType")
                wt = WorkType.objects.get(pk=w.work_type_id)
                if not w.task_type:  # не перезаписываем если уже заполнен из PPWork
                    w.task_type = wt.name
            except Exception:
                pass
        w.save()


def migrate_data_backward(apps, schema_editor):
    """Обратный перенос данных — восстанавливаем PPWork и TaskWork."""
    Work = apps.get_model("works", "Work")
    PPWork = apps.get_model("works", "PPWork")
    TaskWork = apps.get_model("works", "TaskWork")

    for w in Work.objects.filter(show_in_pp=True):
        PPWork.objects.get_or_create(
            work=w,
            defaults=dict(
                task_type=w.task_type or "Выпуск нового документа",
                pp_project_id=w.pp_project_id,
                row_code=w.row_code,
                work_order=w.work_order,
                stage_num=w.stage_num,
                milestone_num=w.milestone_num,
                work_num=w.work_num,
                work_designation=w.work_designation,
                sheets_a4=w.sheets_a4,
                norm=w.norm,
                coeff=w.coeff,
                total_2d=w.total_2d,
                total_3d=w.total_3d,
                labor=w.labor,
                sector_head_name=w.sector_head_name,
            ),
        )

    for w in Work.objects.filter(show_in_plan=True):
        TaskWork.objects.get_or_create(
            work=w,
            defaults=dict(
                stage=w.stage,
                justification=w.justification,
                executors_list=w.executors_list,
                actions=w.actions,
            ),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("works", "0009_fix_coeff_max_digits"),
    ]

    operations = [
        # ── 1. Добавляем новые поля в Work ───────────────────────────────
        migrations.AddField(
            model_name="work",
            name="show_in_pp",
            field=models.BooleanField(default=False, verbose_name="Показывать в ПП"),
        ),
        migrations.AddField(
            model_name="work",
            name="show_in_plan",
            field=models.BooleanField(default=False, verbose_name="Показывать в СП"),
        ),
        # Поля из TaskWork
        migrations.AddField(
            model_name="work",
            name="stage",
            field=models.CharField(
                blank=True, default="", max_length=100, verbose_name="№ Этапа"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="work",
            name="justification",
            field=models.CharField(
                blank=True, default="", max_length=500, verbose_name="Основание"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="work",
            name="executors_list",
            field=models.JSONField(
                blank=True, default=list, verbose_name="Список исполнителей"
            ),
        ),
        migrations.AddField(
            model_name="work",
            name="actions",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="Связи / доп. данные"
            ),
        ),
        # Поля из PPWork
        migrations.AddField(
            model_name="work",
            name="task_type",
            field=models.CharField(
                blank=True, default="", max_length=100, verbose_name="Тип работы"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="work",
            name="pp_project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pp_works",
                to="works.ppproject",
                verbose_name="Проект ПП",
            ),
        ),
        migrations.AddField(
            model_name="work",
            name="row_code",
            field=models.CharField(
                blank=True, default="", max_length=50, verbose_name="Код строки"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="work",
            name="work_order",
            field=models.CharField(
                blank=True, default="", max_length=100, verbose_name="Заказ-наряд"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="work",
            name="stage_num",
            field=models.CharField(
                blank=True, default="", max_length=50, verbose_name="Этап"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="work",
            name="milestone_num",
            field=models.CharField(
                blank=True, default="", max_length=50, verbose_name="Подэтап"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="work",
            name="work_num",
            field=models.CharField(
                blank=True, default="", max_length=50, verbose_name="Номер работы"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="work",
            name="work_designation",
            field=models.CharField(
                blank=True, default="", max_length=200, verbose_name="Обозначение"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="work",
            name="sheets_a4",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=8,
                null=True,
                verbose_name="Листы А4",
            ),
        ),
        migrations.AddField(
            model_name="work",
            name="norm",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=8,
                null=True,
                verbose_name="Норма (чел.-ч)",
            ),
        ),
        migrations.AddField(
            model_name="work",
            name="coeff",
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                max_digits=8,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Коэффициент",
            ),
        ),
        migrations.AddField(
            model_name="work",
            name="total_2d",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=8,
                null=True,
                verbose_name="Трудоёмкость 2D",
            ),
        ),
        migrations.AddField(
            model_name="work",
            name="total_3d",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=8,
                null=True,
                verbose_name="Трудоёмкость 3D",
            ),
        ),
        migrations.AddField(
            model_name="work",
            name="labor",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=8,
                null=True,
                verbose_name="Трудозатраты итого",
            ),
        ),
        migrations.AddField(
            model_name="work",
            name="sector_head_name",
            field=models.CharField(
                blank=True, default="", max_length=200, verbose_name="Начальник сектора"
            ),
            preserve_default=False,
        ),
        # ── 2. Перенос данных ─────────────────────────────────────────────
        migrations.RunPython(migrate_data_forward, migrate_data_backward),
        # ── 3. Удаляем старые поля из Work (перед удалением WorkType!) ──────
        migrations.RemoveField(model_name="work", name="source_type"),
        migrations.RemoveField(model_name="work", name="work_type"),
        # ── 4. Удаляем старые таблицы ─────────────────────────────────────
        migrations.DeleteModel(name="PPWork"),
        migrations.DeleteModel(name="TaskWork"),
        migrations.DeleteModel(name="WorkType"),
        # ── 5. Обновляем индексы ──────────────────────────────────────────
        migrations.AlterModelOptions(
            name="work",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "Работа",
                "verbose_name_plural": "Работы",
            },
        ),
    ]
