"""
Версионирование планов (снимки / baselines).

При каждой итерации (передача в ПП, возврат в сквозной) фиксируется
снимок ключевых полей всех работ сквозного графика.
"""

from django.db import models


class BaselineSnapshot(models.Model):
    """Снимок версии сквозного графика."""

    cross_schedule = models.ForeignKey(
        "enterprise.CrossSchedule",
        on_delete=models.CASCADE,
        related_name="baselines",
        verbose_name="Сквозной график",
    )
    version = models.IntegerField("Номер версии")
    comment = models.TextField("Комментарий", blank=True)
    created_by = models.ForeignKey(
        "employees.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        db_table = "ent_baseline_snapshot"
        verbose_name = "Снимок версии"
        verbose_name_plural = "Снимки версий"
        constraints = [
            models.UniqueConstraint(
                fields=["cross_schedule", "version"],
                name="ent_baseline_sch_ver_uniq",
            ),
        ]
        ordering = ["cross_schedule", "-version"]

    def __str__(self):
        return f"{self.cross_schedule.project} — v{self.version}"


class BaselineEntry(models.Model):
    """
    Запись снимка: ключевые поля одной работы на момент фиксации.

    Поля в data (JSONField):
      date_start, date_end, labor, executor_id, sector_id,
      department_id, stage_num, work_order, status
    """

    snapshot = models.ForeignKey(
        BaselineSnapshot,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="Снимок",
    )
    work = models.ForeignKey(
        "works.Work",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Работа",
    )
    data = models.JSONField("Данные", default=dict)

    class Meta:
        db_table = "ent_baseline_entry"
        verbose_name = "Запись снимка"
        verbose_name_plural = "Записи снимков"

    def __str__(self):
        work_name = self.work.name if self.work else "(удалена)"
        return f"v{self.snapshot.version} / {work_name}"
