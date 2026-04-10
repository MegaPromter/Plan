"""
Data migration: пометить всех существующих сотрудников как созданных admin.
"""

from django.db import migrations


def set_created_by_admin(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Employee = apps.get_model("employees", "Employee")
    admin_user = User.objects.filter(username="admin").first()
    if admin_user:
        Employee.objects.filter(created_by__isnull=True).update(created_by=admin_user)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0009_add_created_by"),
    ]

    operations = [
        migrations.RunPython(set_created_by_admin, reverse_noop),
    ]
