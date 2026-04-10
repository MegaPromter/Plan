"""
Data migration: сбросить created_by для самозарегистрированных пользователей.
"""

from django.db import migrations


def clear_self_registered(apps, schema_editor):
    Employee = apps.get_model("employees", "Employee")

    # Известные самозарегистрированные
    self_registered = [
        ("Русских", "Антон"),
        ("Троицкая", "Юлия"),
    ]
    for last, first in self_registered:
        Employee.objects.filter(last_name=last, first_name=first).update(
            created_by=None
        )

    # Тестовые аккаунты
    test_lastnames = ["Симуоятор", "Кайфовый", "Планировщик"]
    for name in test_lastnames:
        Employee.objects.filter(last_name=name).update(created_by=None)


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0010_set_created_by_admin"),
    ]

    operations = [
        migrations.RunPython(clear_self_registered, migrations.RunPython.noop),
    ]
