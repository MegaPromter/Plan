"""
Data migration: определить самозарегистрированных по Django admin log.
Если для User нет записи 'addition' в LogEntry — значит создан не через админку.
"""
from django.db import migrations


def detect_self_registered(apps, schema_editor):
    Employee = apps.get_model('employees', 'Employee')
    LogEntry = apps.get_model('admin', 'LogEntry')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # ContentType для User
    user_ct = ContentType.objects.filter(app_label='auth', model='user').first()
    if not user_ct:
        return

    # User ID, которые были созданы через админку (есть запись ADDITION в LogEntry)
    # action_flag=1 означает ADDITION (создание)
    admin_created_user_ids = set(
        LogEntry.objects.filter(
            content_type=user_ct,
            action_flag=1,
        ).values_list('object_id', flat=True)
    )

    # Сбрасываем created_by для тех, чей user НЕ был создан через админку
    for emp in Employee.objects.select_related('user').exclude(created_by__isnull=True):
        if emp.user_id and str(emp.user_id) not in admin_created_user_ids:
            emp.created_by = None
            emp.save(update_fields=['created_by'])


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0011_clear_self_registered'),
    ]

    operations = [
        migrations.RunPython(detect_self_registered, migrations.RunPython.noop),
    ]
