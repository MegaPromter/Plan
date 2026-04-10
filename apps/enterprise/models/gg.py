"""
Модели генерального графика (ГГ).

Иерархия:
  GGTemplate → GGTemplateStage  (шаблоны типовых стадий)
  GeneralSchedule → GGStage → GGStageDependency  (ГГ конкретного проекта)
                  → GGMilestone                   (контрольные точки)
"""

from django.db import models


class GGTemplate(models.Model):
    """Шаблон генерального графика (набор типовых стадий)."""

    name = models.CharField("Название шаблона", max_length=200)
    created_by = models.ForeignKey(
        "employees.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        db_table = "ent_gg_template"
        verbose_name = "Шаблон ГГ"
        verbose_name_plural = "Шаблоны ГГ"
        ordering = ["name"]

    def __str__(self):
        return self.name


class GGTemplateStage(models.Model):
    """Стадия в шаблоне ГГ (название + порядок, без сроков)."""

    template = models.ForeignKey(
        GGTemplate,
        on_delete=models.CASCADE,
        related_name="stages",
        verbose_name="Шаблон",
    )
    name = models.CharField("Название стадии", max_length=300)
    order = models.IntegerField("Порядок", default=0)

    class Meta:
        db_table = "ent_gg_template_stage"
        verbose_name = "Стадия шаблона ГГ"
        verbose_name_plural = "Стадии шаблона ГГ"
        ordering = ["template", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "order"],
                name="ent_gg_tpl_stage_order_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.template.name} / {self.name}"


class GeneralSchedule(models.Model):
    """Генеральный график проекта (один на проект)."""

    project = models.OneToOneField(
        "works.Project",
        on_delete=models.CASCADE,
        related_name="general_schedule",
        verbose_name="Проект",
    )
    created_by = models.ForeignKey(
        "employees.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        db_table = "ent_general_schedule"
        verbose_name = "Генеральный график"
        verbose_name_plural = "Генеральные графики"

    def __str__(self):
        return f"ГГ: {self.project}"


class GGStage(models.Model):
    """Стадия генерального графика."""

    schedule = models.ForeignKey(
        GeneralSchedule,
        on_delete=models.CASCADE,
        related_name="stages",
        verbose_name="ГГ",
    )
    name = models.CharField("Название", max_length=300)
    date_start = models.DateField("Дата начала", null=True, blank=True)
    date_end = models.DateField("Дата окончания", null=True, blank=True)
    labor = models.DecimalField(
        "Трудозатраты (ч/ч)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    order = models.IntegerField("Порядок", default=0)
    parent_stage = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_stages",
        verbose_name="Родительская стадия",
    )

    class Meta:
        db_table = "ent_gg_stage"
        verbose_name = "Стадия ГГ"
        verbose_name_plural = "Стадии ГГ"
        ordering = ["schedule", "order"]
        indexes = [
            models.Index(fields=["schedule", "order"], name="ent_gg_stage_sch_ord_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(date_start__isnull=True)
                    | models.Q(date_end__isnull=True)
                    | models.Q(date_end__gte=models.F("date_start"))
                ),
                name="ent_gg_stage_dates_check",
            ),
        ]

    def __str__(self):
        return f"{self.schedule.project} / {self.name}"


class GGMilestone(models.Model):
    """Веха (контрольная точка с нулевой длительностью)."""

    schedule = models.ForeignKey(
        GeneralSchedule,
        on_delete=models.CASCADE,
        related_name="milestones",
        verbose_name="ГГ",
    )
    name = models.CharField("Название", max_length=300)
    date = models.DateField("Дата")
    stage = models.ForeignKey(
        GGStage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="milestones",
        verbose_name="Привязка к стадии",
    )

    class Meta:
        db_table = "ent_gg_milestone"
        verbose_name = "Веха ГГ"
        verbose_name_plural = "Вехи ГГ"

    def __str__(self):
        return f"◇ {self.name} ({self.date})"


class GGStageDependency(models.Model):
    """Связь (зависимость) между стадиями ГГ."""

    DEP_FS = "FS"
    DEP_SS = "SS"
    DEP_FF = "FF"
    DEP_SF = "SF"
    DEP_TYPE_CHOICES = [
        (DEP_FS, "Финиш-Старт"),
        (DEP_SS, "Старт-Старт"),
        (DEP_FF, "Финиш-Финиш"),
        (DEP_SF, "Старт-Финиш"),
    ]

    predecessor = models.ForeignKey(
        GGStage,
        on_delete=models.CASCADE,
        related_name="successor_deps",
        verbose_name="Предшественник",
    )
    successor = models.ForeignKey(
        GGStage,
        on_delete=models.CASCADE,
        related_name="predecessor_deps",
        verbose_name="Последователь",
    )
    dep_type = models.CharField(
        "Тип связи",
        max_length=2,
        choices=DEP_TYPE_CHOICES,
        default=DEP_FS,
    )
    lag_days = models.IntegerField("Задержка (дней)", default=0)

    class Meta:
        db_table = "ent_gg_stage_dependency"
        verbose_name = "Связь стадий ГГ"
        verbose_name_plural = "Связи стадий ГГ"
        constraints = [
            models.UniqueConstraint(
                fields=["predecessor", "successor"],
                name="ent_gg_dep_pair_uniq",
            ),
            models.CheckConstraint(
                check=~models.Q(predecessor=models.F("successor")),
                name="ent_gg_dep_no_self_link",
            ),
        ]

    def __str__(self):
        return f"{self.predecessor.name} → {self.successor.name} ({self.dep_type})"
