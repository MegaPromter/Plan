"""
Data migration: сбросить created_by для самозарегистрированных.
"""
from django.db import migrations


def clear_self_registered(apps, schema_editor):
    Employee = apps.get_model('employees', 'Employee')

    self_registered = [
        ('Перфильев', 'Андрей'),
        ('Вет', 'Серг'),
        ('Жедяев', 'Юрий'),
        ('Цезарь', 'Гай'),
        ('Беляков', 'Андрей'),
        ('Постнов', 'Михаил'),
        ('Томилин', 'Сергей'),
    ]
    for last_name, first_name in self_registered:
        Employee.objects.filter(
            last_name=last_name, first_name=first_name
        ).update(created_by=None)


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0013_fix_created_by'),
    ]

    operations = [
        migrations.RunPython(clear_self_registered, migrations.RunPython.noop),
    ]
