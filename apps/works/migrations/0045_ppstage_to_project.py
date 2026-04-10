"""Переносит PPStage.pp_project FK → PPStage.project FK (Project УП)."""

import django.db.models.deletion
from django.db import migrations, models


def migrate_pp_to_project(apps, schema_editor):
    """Копирует pp_project.up_project → project для каждого PPStage."""
    PPStage = apps.get_model("works", "PPStage")
    for stage in PPStage.objects.select_related("pp_project").all():
        if stage.pp_project and stage.pp_project.up_project_id:
            stage.project_id = stage.pp_project.up_project_id
            stage.save(update_fields=["project_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("works", "0044_ppstage_model"),
    ]

    operations = [
        # 1. Добавляем новое поле project (nullable временно)
        migrations.AddField(
            model_name="ppstage",
            name="project",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="stages",
                to="works.project",
                verbose_name="Проект УП",
            ),
        ),
        # 2. Мигрируем данные
        migrations.RunPython(migrate_pp_to_project, migrations.RunPython.noop),
        # 3. Удаляем старое поле pp_project
        migrations.RemoveField(
            model_name="ppstage",
            name="pp_project",
        ),
        # 4. Делаем project NOT NULL
        migrations.AlterField(
            model_name="ppstage",
            name="project",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="stages",
                to="works.project",
                verbose_name="Проект УП",
            ),
        ),
    ]
