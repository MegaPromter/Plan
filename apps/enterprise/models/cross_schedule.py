"""
Модели сквозного графика.

Иерархия:
  CrossSchedule (один на проект)
    → CrossStage (этапы, ссылаются на стадии ГГ)
    → CrossMilestone (вехи)
    → CrossScheduleDeptStatus (статус по подразделениям при гранулярности Б)

Работы (Work) привязываются к CrossStage через FK work.cross_stage.
"""
from django.db import models


class CrossSchedule(models.Model):
    """Сквозной график проекта (один на проект)."""

    EDIT_CROSS = 'cross'
    EDIT_PP = 'pp'
    EDIT_LOCKED = 'locked'
    EDIT_OWNER_CHOICES = [
        (EDIT_CROSS, 'Сквозной график'),
        (EDIT_PP, 'Производственные планы'),
        (EDIT_LOCKED, 'Заблокирован (финал)'),
    ]

    GRAN_WHOLE = 'whole'
    GRAN_PER_DEPT = 'per_dept'
    GRANULARITY_CHOICES = [
        (GRAN_WHOLE, 'Весь график'),
        (GRAN_PER_DEPT, 'По подразделениям'),
    ]

    project = models.OneToOneField(
        'works.Project', on_delete=models.CASCADE,
        related_name='cross_schedule', verbose_name='Проект',
    )
    created_by = models.ForeignKey(
        'employees.Employee', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Создал',
    )
    version = models.IntegerField('Номер итерации', default=1)
    edit_owner = models.CharField(
        'Владелец редактирования', max_length=10,
        choices=EDIT_OWNER_CHOICES, default=EDIT_CROSS,
    )
    granularity = models.CharField(
        'Гранулярность блокировки', max_length=10,
        choices=GRANULARITY_CHOICES, default=GRAN_WHOLE,
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        db_table = 'ent_cross_schedule'
        verbose_name = 'Сквозной график'
        verbose_name_plural = 'Сквозные графики'

    def __str__(self):
        return f'Сквозной: {self.project} (v{self.version})'


class CrossScheduleDeptStatus(models.Model):
    """
    Статус подразделения при гранулярности «по подразделениям».
    Отслеживает, в каком состоянии находится конкретное подразделение
    в рамках текущей итерации.
    """
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RETURNED = 'returned'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Передано'),
        (STATUS_IN_PROGRESS, 'В работе'),
        (STATUS_RETURNED, 'Возвращено'),
    ]

    cross_schedule = models.ForeignKey(
        CrossSchedule, on_delete=models.CASCADE,
        related_name='dept_statuses', verbose_name='Сквозной график',
    )
    department = models.ForeignKey(
        'employees.Department', on_delete=models.CASCADE,
        verbose_name='Подразделение',
    )
    status = models.CharField(
        'Статус', max_length=20,
        choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        db_table = 'ent_cross_dept_status'
        verbose_name = 'Статус подразделения'
        verbose_name_plural = 'Статусы подразделений'
        constraints = [
            models.UniqueConstraint(
                fields=['cross_schedule', 'department'],
                name='ent_cross_dept_status_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.cross_schedule.project} / {self.department} — {self.get_status_display()}'


class CrossStage(models.Model):
    """
    Пункт или этап сквозного графика.

    Иерархия:
      Пункт (parent_item=NULL, gg_stage → GGStage) — копия пункта ГГ
        → Этап (parent_item → пункт) — детализация пункта, нумерация А.Б

    Работы (Work) привязываются к этапу через FK work.cross_stage.
    """
    cross_schedule = models.ForeignKey(
        CrossSchedule, on_delete=models.CASCADE,
        related_name='stages', verbose_name='Сквозной график',
    )
    gg_stage = models.ForeignKey(
        'enterprise.GGStage', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cross_stages',
        verbose_name='Пункт ГГ',
    )
    parent_item = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='sub_stages',
        verbose_name='Родительский пункт',
    )
    name = models.CharField('Название', max_length=300)
    date_start = models.DateField('Дата начала', null=True, blank=True)
    date_end = models.DateField('Дата окончания', null=True, blank=True)
    department = models.ForeignKey(
        'employees.Department', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Подразделение',
    )
    order = models.IntegerField('Порядок', default=0)

    class Meta:
        db_table = 'ent_cross_stage'
        verbose_name = 'Этап сквозного графика'
        verbose_name_plural = 'Этапы сквозного графика'
        ordering = ['cross_schedule', 'order']
        indexes = [
            models.Index(
                fields=['cross_schedule', 'order'],
                name='ent_cross_stage_sch_ord_idx',
            ),
            models.Index(fields=['department'], name='ent_cross_stage_dept_idx'),
            models.Index(fields=['gg_stage'], name='ent_cross_stage_gg_idx'),
        ]

    def __str__(self):
        return f'{self.cross_schedule.project} / {self.name}'


class CrossMilestone(models.Model):
    """Веха сквозного графика (контрольная точка, нулевая длительность)."""
    cross_schedule = models.ForeignKey(
        CrossSchedule, on_delete=models.CASCADE,
        related_name='milestones', verbose_name='Сквозной график',
    )
    name = models.CharField('Название', max_length=300)
    date = models.DateField('Дата')
    cross_stage = models.ForeignKey(
        CrossStage, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='milestones',
        verbose_name='Привязка к этапу',
    )

    class Meta:
        db_table = 'ent_cross_milestone'
        verbose_name = 'Веха сквозного графика'
        verbose_name_plural = 'Вехи сквозного графика'

    def __str__(self):
        return f'◇ {self.name} ({self.date})'
