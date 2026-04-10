"""
Migration: add WorkCalendar and AuditLog models.
"""

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("works", "0004_add_performance_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkCalendar",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("year", models.PositiveSmallIntegerField(verbose_name="Год")),
                (
                    "month",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(12),
                        ],
                        verbose_name="Месяц",
                    ),
                ),
                (
                    "hours_norm",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=6,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="Норма часов",
                    ),
                ),
            ],
            options={
                "verbose_name": "Норма рабочих часов",
                "verbose_name_plural": "Производственный календарь",
                "db_table": "work_calendar",
                "ordering": ["-year", "month"],
                "unique_together": {("year", "month")},
            },
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("task_create", "Создание задачи"),
                            ("task_update", "Изменение задачи"),
                            ("task_delete", "Удаление задачи"),
                            ("pp_sync", "Синхронизация ПП"),
                            ("pp_create", "Создание записи ПП"),
                            ("pp_delete", "Удаление записи ПП"),
                            ("role_change", "Смена роли пользователя"),
                            ("user_create", "Создание пользователя"),
                            ("user_delete", "Удаление пользователя"),
                        ],
                        max_length=30,
                        verbose_name="Действие",
                    ),
                ),
                (
                    "object_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID объекта"
                    ),
                ),
                (
                    "object_repr",
                    models.CharField(blank=True, max_length=500, verbose_name="Объект"),
                ),
                (
                    "details",
                    models.JSONField(blank=True, default=dict, verbose_name="Детали"),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(
                        blank=True, null=True, verbose_name="IP-адрес"
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Время"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Запись журнала",
                "verbose_name_plural": "Журнал аудита",
                "db_table": "work_audit_log",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["action"], name="audit_action_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["user"], name="audit_user_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["created_at"], name="audit_created_idx"),
        ),
    ]
