"""Seed task_type entries in Directory so validation works on fresh deploys."""

from django.db import migrations


TASK_TYPES = [
    'Выпуск нового документа',
    'Корректировка документа',
    'Разработка',
    'Сопровождение (ОКАН)',
]


def seed_task_types(apps, schema_editor):
    Directory = apps.get_model('works', 'Directory')
    for value in TASK_TYPES:
        Directory.objects.get_or_create(dir_type='task_type', value=value)


def remove_task_types(apps, schema_editor):
    Directory = apps.get_model('works', 'Directory')
    Directory.objects.filter(dir_type='task_type', value__in=TASK_TYPES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0031_product_name_short'),
    ]

    operations = [
        migrations.RunPython(seed_task_types, remove_task_types),
    ]
