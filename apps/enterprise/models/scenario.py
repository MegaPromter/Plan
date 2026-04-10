"""
Сценарное планирование (What-If).

Песочница: изолированная копия ключевых полей работ для моделирования
влияния перспективных проектов на загрузку предприятия.
"""

from django.db import models


class Scenario(models.Model):
    """Сценарий What-If."""

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Черновик"),
        (STATUS_ACTIVE, "Активный"),
        (STATUS_ARCHIVED, "Архив"),
    ]

    name = models.CharField("Название", max_length=200)
    project = models.ForeignKey(
        "works.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scenarios",
        verbose_name="Проект",
    )
    created_by = models.ForeignKey(
        "employees.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Создал",
    )
    status = models.CharField(
        "Статус",
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        db_table = "ent_scenario"
        verbose_name = "Сценарий What-If"
        verbose_name_plural = "Сценарии What-If"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class ScenarioEntry(models.Model):
    """
    Запись сценария: копия ключевых полей работы.
    work=NULL для работ, добавленных только в сценарии (новый проект).
    """

    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="Сценарий",
    )
    work = models.ForeignKey(
        "works.Work",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Оригинал работы",
    )
    data = models.JSONField("Данные", default=dict)

    class Meta:
        db_table = "ent_scenario_entry"
        verbose_name = "Запись сценария"
        verbose_name_plural = "Записи сценариев"

    def __str__(self):
        return f'{self.scenario.name} / {self.work or "(новая)"}'
