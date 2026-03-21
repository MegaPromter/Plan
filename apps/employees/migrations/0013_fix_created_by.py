"""
Data migration: исправить created_by после ошибочной миграции 0012.
1. Вернуть всех к created_by=admin
2. Сбросить только реально самозарегистрированных (Русских, Троицкая)
"""
from django.db import migrations


def fix_created_by(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Employee = apps.get_model('employees', 'Employee')

    admin_user = User.objects.filter(username='admin').first()
    if not admin_user:
        return

    # Шаг 1: пометить ВСЕХ как созданных admin
    Employee.objects.all().update(created_by=admin_user)

    # Шаг 2: сбросить для самозарегистрированных
    self_registered = [
        ('Русских', 'Антон'),
        ('Троицкая', 'Юлия'),
    ]
    for last_name, first_name in self_registered:
        Employee.objects.filter(
            last_name=last_name, first_name=first_name
        ).update(created_by=None)


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0012_detect_self_registered'),
    ]

    operations = [
        migrations.RunPython(fix_created_by, migrations.RunPython.noop),
    ]
