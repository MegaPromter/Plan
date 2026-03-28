"""
Модели приложения works.

Архитектура таблицы работ:
  Work — единая таблица для всех записей.
  show_in_pp   = True  → строка производственного плана
  show_in_plan = True  → задача сводного плана
  Одна запись может быть видна в обоих модулях одновременно.

TaskExecutor — дополнительные исполнители задачи (FK → Work).
WorkReport   — отчётные документы (FK → Work).
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.employees.models import Department, Employee, NTCCenter, Sector

User = get_user_model()


# ── Универсальный справочник ───────────────────────────────────────────────────

class Directory(models.Model):
    """
    Универсальная таблица справочников.
    Типы: center, position, dept, sector, executor, task_type, justification.
    """
    TYPE_CHOICES = [
        ('center',        'НТЦ-центр'),
        ('position',      'Должность'),
        ('dept',          'Отдел'),
        ('sector',        'Сектор'),
        ('executor',      'Исполнитель'),
        ('task_type',     'Тип работы'),
        ('justification', 'Обоснование'),
        ('project',       'Проект'),
        ('milestone',     'Этап'),
        ('stage',         'Веха'),
        ('substage',      'Работа'),
    ]

    dir_type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES)
    value    = models.CharField('Значение', max_length=500)
    parent   = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='children', verbose_name='Родитель',
    )

    class Meta:
        db_table     = 'work_directory'
        verbose_name = 'Справочник'
        verbose_name_plural = 'Справочники'
        ordering = ['dir_type', 'value']
        indexes = [
            models.Index(fields=['dir_type']),
            models.Index(fields=['dir_type', 'value']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        return f'[{self.dir_type}] {self.value}'


# ── Проекты производственного плана ───────────────────────────────────────────

class PPProject(models.Model):
    """Производственный план — группирует строки ПП."""
    name       = models.CharField('Название плана', max_length=255)
    directory  = models.ForeignKey(
        Directory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pp_projects', verbose_name='Связь со справочником',
    )
    up_project = models.ForeignKey(
        'Project', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pp_plans', verbose_name='Проект УП',
    )
    up_product = models.ForeignKey(
        'ProjectProduct', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pp_plans', verbose_name='Изделие УП',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        db_table     = 'work_pp_project'
        verbose_name = 'Проект ПП'
        verbose_name_plural = 'Проекты ПП'
        ordering = ['name']

    def __str__(self):
        return self.name


# ── Справочники проектов УП ────────────────────────────────────────────────────

class Project(models.Model):
    """Проект (модуль Управления проектами)."""

    # ── Статусы проекта (Enterprise) ─────────────────────────────────────
    STATUS_PROSPECTIVE = 'prospective'
    STATUS_APPROVED    = 'approved'
    STATUS_ACTIVE      = 'active'
    STATUS_SUSPENDED   = 'suspended'
    STATUS_DEFERRED    = 'deferred'
    STATUS_CLOSED      = 'closed'
    STATUS_CANCELLED   = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PROSPECTIVE, 'Перспективный'),
        (STATUS_APPROVED,    'Одобренный'),
        (STATUS_ACTIVE,      'Действующий'),
        (STATUS_SUSPENDED,   'Приостановленный'),
        (STATUS_DEFERRED,    'Отложенный'),
        (STATUS_CLOSED,      'Закрытый'),
        (STATUS_CANCELLED,   'Отменённый'),
    ]

    PRIORITY_CRITICAL = 'critical'
    PRIORITY_HIGH     = 'high'
    PRIORITY_MEDIUM   = 'medium'
    PRIORITY_LOW      = 'low'
    PRIORITY_CHOICES = [
        (PRIORITY_CRITICAL, 'Критический'),
        (PRIORITY_HIGH,     'Высокий'),
        (PRIORITY_MEDIUM,   'Средний'),
        (PRIORITY_LOW,      'Низкий'),
    ]

    # ── Основные поля ────────────────────────────────────────────────────
    name_full  = models.CharField('Полное наименование', max_length=500)
    name_short = models.CharField('Краткое наименование', max_length=100, blank=True)
    code       = models.CharField('Шифр / код', max_length=100, blank=True)
    row_code_seq = models.PositiveIntegerField('Счётчик row_code', default=0)

    # ── Поля Enterprise ──────────────────────────────────────────────────
    status = models.CharField(
        'Статус проекта', max_length=20,
        choices=STATUS_CHOICES, default=STATUS_ACTIVE,
    )
    priority_number = models.IntegerField(
        'Числовой приоритет', null=True, blank=True,
    )
    priority_category = models.CharField(
        'Категория приоритета', max_length=10,
        choices=PRIORITY_CHOICES, null=True, blank=True,
    )
    chief_designer = models.ForeignKey(
        'employees.Employee', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='chief_designer_projects',
        verbose_name='Главный конструктор',
    )

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        db_table     = 'work_project'
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'
        ordering = ['name_short', 'name_full']

    def __str__(self):
        return self.name_short or self.name_full

    @property
    def name(self):
        """Обратная совместимость."""
        return self.name_short or self.name_full


class ProjectProduct(models.Model):
    """Изделие / объект в рамках проекта."""
    project    = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='products', verbose_name='Проект',
    )
    name       = models.CharField('Наименование изделия', max_length=255)
    name_short = models.CharField('Краткое наименование', max_length=100, blank=True)
    code       = models.CharField('Шифр', max_length=100, blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        db_table     = 'work_project_product'
        verbose_name = 'Изделие проекта'
        verbose_name_plural = 'Изделия проекта'
        ordering = ['name']

    def __str__(self):
        return f'{self.code} — {self.name}' if self.code else self.name


# ── Основная таблица работ ────────────────────────────────────────────────────

class Work(models.Model):
    """
    Единая запись о работе.
    show_in_pp=True   — отображается в производственном плане.
    show_in_plan=True — отображается в сводном плане задач.
    Запись может быть видна в обоих модулях одновременно.
    """

    # ── Флаги видимости ────────────────────────────────────────────────────
    show_in_pp   = models.BooleanField('Показывать в ПП',  default=False)
    show_in_plan = models.BooleanField('Показывать в СП',  default=False)

    # ── Принадлежность ────────────────────────────────────────────────────
    ntc_center = models.ForeignKey(
        NTCCenter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='works', verbose_name='НТЦ-центр',
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='works', verbose_name='Отдел',
    )
    sector = models.ForeignKey(
        Sector, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='works', verbose_name='Сектор',
    )
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='works', verbose_name='Проект',
    )

    # ── Тип работы (текстом) ──────────────────────────────────────────────
    # Заменяет бывший FK work_type → WorkType и бывший PPWork.task_type
    task_type = models.CharField('Тип работы', max_length=100, blank=True, default='')

    # ── Основные поля ─────────────────────────────────────────────────────
    work_name    = models.CharField('Наименование работы', max_length=500)
    # work_num и work_designation — единые поля (и для ПП, и для СП)
    # определены ниже в блоке «Поля производственного плана»

    # ── Исполнитель ───────────────────────────────────────────────────────
    executor = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='works', verbose_name='Исполнитель',
    )

    # ── Сроки ─────────────────────────────────────────────────────────────
    date_start = models.DateField('Начало работы', null=True, blank=True)
    date_end   = models.DateField('Конец работы',  null=True, blank=True)
    deadline   = models.DateField('Контрольный срок', null=True, blank=True)

    # ── Плановые часы по месяцам {«YYYY-MM»: hours} ───────────────────────
    plan_hours = models.JSONField(
        'Плановые часы (по месяцам)', default=dict, blank=True,
    )

    # ── Поля сводного плана (бывший TaskWork) ─────────────────────────────
    # stage_num — единое поле этапа (и для ПП, и для СП), определено ниже
    justification  = models.CharField('Основание', max_length=500, blank=True)
    executors_list = models.JSONField('Список исполнителей', default=list, blank=True)
    actions        = models.JSONField('Связи / доп. данные', default=dict, blank=True)

    # ── Привязка к сквозному графику (Enterprise) ──────────────────────
    cross_stage = models.ForeignKey(
        'enterprise.CrossStage', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='works',
        verbose_name='Этап сквозного графика',
    )

    # ── Поля ПП (+ единые поля stage_num, work_num, work_designation) ────
    pp_project = models.ForeignKey(
        PPProject, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pp_works', verbose_name='Проект ПП',
    )
    row_code         = models.CharField('Код строки',   max_length=50,  blank=True)
    work_order       = models.CharField('Заказ-наряд',  max_length=100, blank=True)
    # Единые поля для ПП и СП (заполняются и отображаются в обоих модулях)
    stage_num        = models.CharField('Этап',         max_length=50,  blank=True)
    milestone_num    = models.CharField('Веха',          max_length=50,  blank=True)
    work_num         = models.CharField('Номер работы', max_length=50,  blank=True)
    work_designation = models.CharField('Обозначение',  max_length=200, blank=True)
    sheets_a4 = models.DecimalField(
        'Листы А4', max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    norm = models.DecimalField(
        'Норма (чел.-ч)', max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    coeff = models.DecimalField(
        'Коэффициент', max_digits=12, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    total_2d = models.DecimalField(
        'Трудоёмкость 2D', max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    total_3d = models.DecimalField(
        'Трудоёмкость 3D', max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    labor = models.DecimalField(
        'Трудозатраты итого', max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )

    # ── Аудит ─────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_works', verbose_name='Создал',
    )
    created_at = models.DateTimeField('Создана',  auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        db_table     = 'work_work'
        verbose_name = 'Работа'
        verbose_name_plural = 'Работы'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['show_in_pp']),
            models.Index(fields=['show_in_plan']),
            models.Index(fields=['department']),
            models.Index(fields=['executor']),
            models.Index(fields=['date_start', 'date_end']),
            models.Index(fields=['show_in_plan', 'deadline']),
            models.Index(fields=['deadline']),
            models.Index(fields=['pp_project']),
            models.Index(fields=['show_in_pp', 'department']),
            models.Index(fields=['show_in_plan', 'department']),
            models.Index(fields=['show_in_pp', 'created_at']),
            models.Index(fields=['executor', 'show_in_plan']),
            models.Index(fields=['date_end', 'show_in_plan'], name='idx_work_date_end_plan'),
        ]
        constraints = [
            # show_in_pp=True → pp_project обязан быть заполнен
            models.CheckConstraint(
                check=Q(show_in_pp=False) | ~Q(pp_project=None),
                name='work_pp_requires_project',
            ),
        ]

    def __str__(self):
        flags = []
        if self.show_in_pp:
            flags.append('ПП')
        if self.show_in_plan:
            flags.append('СП')
        prefix = '/'.join(flags) if flags else '?'
        return f'[{prefix}] {self.work_name}'

    @property
    def total_plan_hours(self) -> float:
        """Сумма плановых часов по всем месяцам."""
        return sum(float(v) for v in self.plan_hours.values())

    @property
    def computed_labor(self):
        """Расчётная трудоёмкость: norm * coeff (если labor не задан явно)."""
        if self.labor is not None:
            return self.labor
        if self.norm is not None and self.coeff is not None:
            return self.norm * self.coeff
        return None


# ── Множественные исполнители задачи ─────────────────────────────────────────

class TaskExecutor(models.Model):
    """
    Дополнительные исполнители задачи.
    Каждый имеет своё распределение часов по месяцам.
    """
    work          = models.ForeignKey(
        Work, on_delete=models.CASCADE,
        related_name='task_executors', verbose_name='Работа',
    )
    executor      = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='task_executor_entries', verbose_name='Исполнитель',
    )
    executor_name = models.CharField('ФИО исполнителя', max_length=200)
    plan_hours    = models.JSONField(
        'Плановые часы (по месяцам)', default=dict, blank=True,
    )

    class Meta:
        db_table     = 'work_task_executor'
        verbose_name = 'Исполнитель задачи'
        verbose_name_plural = 'Исполнители задач'
        indexes = [
            models.Index(fields=['work']),
            models.Index(fields=['executor']),
            models.Index(fields=['work', 'executor'], name='idx_taskexec_work_exec'),
        ]

    def __str__(self):
        name = self.executor.full_name if self.executor else self.executor_name
        return f'{name} → {self.work.work_name}'


# ── Зависимости между задачами ───────────────────────────────────────────────

class TaskDependency(models.Model):
    """
    Зависимость между работами (предшественник → последователь).
    Типы связей:
      FS — Окончание–Начало (Finish-to-Start)   [по умолчанию]
      SS — Начало–Начало   (Start-to-Start)
      FF — Окончание–Окончание (Finish-to-Finish)
      SF — Начало–Окончание (Start-to-Finish)
    lag_days — смещение в днях (может быть отрицательным = опережение).
    """
    TYPE_FS = 'FS'
    TYPE_SS = 'SS'
    TYPE_FF = 'FF'
    TYPE_SF = 'SF'
    TYPE_CHOICES = [
        (TYPE_FS, 'Окончание–Начало (FS)'),
        (TYPE_SS, 'Начало–Начало (SS)'),
        (TYPE_FF, 'Окончание–Окончание (FF)'),
        (TYPE_SF, 'Начало–Окончание (SF)'),
    ]

    predecessor = models.ForeignKey(
        Work, on_delete=models.CASCADE,
        related_name='successor_links',
        verbose_name='Предшественник',
    )
    successor = models.ForeignKey(
        Work, on_delete=models.CASCADE,
        related_name='predecessor_links',
        verbose_name='Последователь',
    )
    dep_type = models.CharField(
        'Тип связи', max_length=2,
        choices=TYPE_CHOICES, default=TYPE_FS,
    )
    lag_days = models.IntegerField('Лаг (дней)', default=0)
    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        db_table = 'work_task_dependency'
        verbose_name = 'Зависимость задач'
        verbose_name_plural = 'Зависимости задач'
        indexes = [
            models.Index(fields=['predecessor']),
            models.Index(fields=['successor']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['predecessor', 'successor'],
                name='work_task_dependency_pred_succ_uniq',
            ),
            models.CheckConstraint(
                check=~models.Q(predecessor=models.F('successor')),
                name='dep_no_self_link',
            ),
        ]

    def __str__(self):
        return f'{self.predecessor_id} → {self.successor_id} ({self.dep_type}, lag={self.lag_days})'


# ── Отчётные документы к работе ──────────────────────────────────────────────

class WorkReport(models.Model):
    """Выпущенный документ / акт по работе."""

    DOC_TYPE_CHOICES = [
        ('design',    'Конструкторский'),
        ('tech',      'Технологический'),
        ('report',    'Отчёт'),
        ('program',   'Программа испытаний'),
        ('other',     'Прочее'),
    ]
    DOC_CLASS_CHOICES = [
        ('original',  'Подлинник'),
        ('copy',      'Копия'),
        ('draft',     'Черновик'),
    ]

    work             = models.ForeignKey(
        Work, on_delete=models.CASCADE,
        related_name='reports', verbose_name='Работа',
    )
    doc_name         = models.CharField('Наименование документа', max_length=500, blank=True)
    doc_designation  = models.CharField('Обозначение',            max_length=200, blank=True)
    ii_pi            = models.CharField('ИИ/ПИ', max_length=10, blank=True)
    doc_number       = models.CharField('Номер изв.', max_length=200, blank=True)
    inventory_num    = models.CharField('Инв. номер',              max_length=100, blank=True)
    date_accepted    = models.DateField('Дата выпуска', null=True, blank=True)
    date_expires     = models.DateField('Срок действия', null=True, blank=True)
    doc_type         = models.CharField('Вид документа',  max_length=20,
                                        choices=DOC_TYPE_CHOICES, blank=True, default='')
    doc_class        = models.CharField('Класс документа', max_length=20,
                                        choices=DOC_CLASS_CHOICES, blank=True, default='')
    sheets_a4        = models.PositiveIntegerField('Листов А4', null=True, blank=True)
    norm             = models.DecimalField('Норма',        max_digits=8, decimal_places=2,
                                           null=True, blank=True)
    coeff            = models.DecimalField('Коэффициент',  max_digits=5, decimal_places=3,
                                           null=True, blank=True)
    bvd_hours        = models.DecimalField('Часы БВД',     max_digits=8, decimal_places=2,
                                           null=True, blank=True)
    norm_control     = models.CharField('Нормоконтролёр', max_length=200, blank=True)
    doc_link         = models.URLField('Ссылка на документ', blank=True)
    created_at       = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        db_table     = 'work_report'
        verbose_name = 'Отчётный документ'
        verbose_name_plural = 'Отчётные документы'
        ordering = ['-date_accepted']
        indexes = [
            models.Index(fields=['work'], name='idx_report_work'),
            models.Index(fields=['work', 'doc_type'], name='idx_report_work_doctype'),
        ]

    def __str__(self):
        return self.doc_name or f'Документ #{self.pk}'


# ── Журнал извещений ──────────────────────────────────────────────────────────

class Notice(models.Model):
    """Журнал корректирующих извещений.

    Два режима:
    1. Автоматический — work_report заполнен. Поля ИИ/ПИ, номер, даты,
       наименование, обозначение, отдел, сектор, разработчик читаются
       из цепочки WorkReport → Work.
    2. Ручной — work_report = NULL. Все поля вводятся вручную.
    """

    STATUS_ACTIVE        = 'active'
    STATUS_EXPIRED       = 'expired'
    STATUS_CLOSED_NO     = 'closed_no'
    STATUS_CLOSED_YES    = 'closed_yes'
    STATUS_CHOICES  = [
        (STATUS_ACTIVE,     'Действует'),
        (STATUS_EXPIRED,    'Просрочено'),
        (STATUS_CLOSED_NO,  'Погашено без внесения'),
        (STATUS_CLOSED_YES, 'Погашено с внесением'),
    ]

    # ── Связь с ЕТБД (для автоматических записей) ──────────────────────────
    work_report = models.OneToOneField(
        WorkReport, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='notice', verbose_name='Отчётный документ',
    )

    # ── Поля для ручного ввода (используются когда work_report=NULL) ───────
    notice_number    = models.CharField('№ ПИ', max_length=100, blank=True)
    ii_pi            = models.CharField('ИИ/ПИ', max_length=10, blank=True)
    notice_type      = models.CharField('Тип извещения', max_length=100, blank=True)
    group            = models.CharField('Группа', max_length=200, blank=True)
    doc_designation  = models.CharField('Обозначение', max_length=200, blank=True)
    department   = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notices', verbose_name='Отдел',
    )
    sector       = models.ForeignKey(
        Sector, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notices', verbose_name='Сектор',
    )
    executor     = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notices', verbose_name='Разработчик',
    )
    date_issued  = models.DateField('Дата выпуска', null=True, blank=True)
    date_expires = models.DateField('Срок действия', null=True, blank=True)
    subject      = models.CharField('Тема', max_length=500, blank=True)

    # ── Собственные поля ───────────────────────────────────────────────────
    description  = models.TextField('Описание', blank=True)
    status       = models.CharField('Статус', max_length=20,
                                    choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    # ── Реквизиты погашения ────────────────────────────────────────────────
    closure_notice_number = models.CharField(
        '№ документа погашения', max_length=100, blank=True,
    )
    closure_date_issued = models.DateField(
        'Дата документа погашения', null=True, blank=True,
    )
    closure_executor = models.CharField(
        'Исполнитель погашения', max_length=200, blank=True,
    )

    created_at   = models.DateTimeField('Создан', auto_now_add=True)
    updated_at   = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        db_table     = 'work_notice'
        verbose_name = 'Извещение'
        verbose_name_plural = 'Журнал извещений'
        ordering = ['-date_issued']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['department']),
            models.Index(fields=['notice_number', 'ii_pi']),
        ]

    def __str__(self):
        return f'[{self.status}] {self.subject or self.notice_type}'

    @property
    def is_auto(self):
        """Привязана ли запись к отчёту (автоматическая)."""
        return self.work_report_id is not None

    @property
    def computed_status(self):
        """Вычисляемый статус с учётом сроков действия ПИ."""
        if self.status in (self.STATUS_CLOSED_NO, self.STATUS_CLOSED_YES):
            return self.status
        # Определяем ii_pi и date_expires из нужного источника
        if self.is_auto:
            wr = self.work_report
            ii_pi = wr.ii_pi if wr else ''
            expires = wr.date_expires if wr else None
        else:
            ii_pi = self.ii_pi
            expires = self.date_expires
        if ii_pi == 'ПИ' and expires:
            if expires < timezone.now().date():
                return self.STATUS_EXPIRED
        return self.STATUS_ACTIVE


# ── Производственный календарь ───────────────────────────────────────────────

class WorkCalendar(models.Model):
    """Норма рабочих часов для одного человека в календарном месяце."""
    year  = models.PositiveSmallIntegerField('Год')
    month = models.PositiveSmallIntegerField(
        'Месяц',
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    hours_norm = models.DecimalField(
        'Норма часов', max_digits=6, decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        db_table         = 'work_calendar'
        verbose_name     = 'Норма рабочих часов'
        verbose_name_plural = 'Производственный календарь'
        ordering         = ['-year', 'month']
        constraints = [
            models.UniqueConstraint(
                fields=['year', 'month'],
                name='work_calendar_year_month_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.year}-{self.month:02d}: {self.hours_norm}ч'

    @property
    def month_key(self) -> str:
        return f'{self.year}-{self.month:02d}'


class Holiday(models.Model):
    """Нерабочий/праздничный день производственного календаря."""
    date = models.DateField('Дата', unique=True)
    name = models.CharField('Название', max_length=200, blank=True, default='')

    class Meta:
        db_table = 'work_holiday'
        verbose_name = 'Нерабочий день'
        verbose_name_plural = 'Нерабочие дни'
        ordering = ['date']

    def __str__(self):
        return f'{self.date} — {self.name}' if self.name else str(self.date)


# ── Журнал действий пользователей ────────────────────────────────────────────

class AuditLog(models.Model):
    """Журнал действий пользователей для аудита."""

    ACTION_TASK_CREATE   = 'task_create'
    ACTION_TASK_UPDATE   = 'task_update'
    ACTION_TASK_DELETE   = 'task_delete'
    ACTION_PP_SYNC       = 'pp_sync'
    ACTION_PP_CREATE     = 'pp_create'
    ACTION_PP_UPDATE     = 'pp_update'
    ACTION_PP_DELETE     = 'pp_delete'
    ACTION_ROLE_CHANGE   = 'role_change'
    ACTION_USER_CREATE   = 'user_create'
    ACTION_USER_DELETE   = 'user_delete'
    ACTION_DEP_CREATE    = 'dep_create'
    ACTION_DEP_UPDATE    = 'dep_update'
    ACTION_DEP_DELETE    = 'dep_delete'
    ACTION_DEP_ALIGN     = 'dep_align'
    ACTION_CS_CREATE     = 'cs_create'
    ACTION_CS_SUBMIT     = 'cs_submit'
    ACTION_CS_APPROVE    = 'cs_approve'
    ACTION_CS_REJECT     = 'cs_reject'
    ACTION_COMMENT_DELETE = 'comment_delete'

    ACTION_CHOICES = [
        (ACTION_TASK_CREATE, 'Создание задачи'),
        (ACTION_TASK_UPDATE, 'Изменение задачи'),
        (ACTION_TASK_DELETE, 'Удаление задачи'),
        (ACTION_PP_SYNC,     'Синхронизация ПП'),
        (ACTION_PP_CREATE,   'Создание записи ПП'),
        (ACTION_PP_UPDATE,   'Изменение записи ПП'),
        (ACTION_PP_DELETE,   'Удаление записи ПП'),
        (ACTION_ROLE_CHANGE, 'Смена роли пользователя'),
        (ACTION_USER_CREATE, 'Создание пользователя'),
        (ACTION_USER_DELETE, 'Удаление пользователя'),
        (ACTION_DEP_CREATE,  'Создание зависимости'),
        (ACTION_DEP_UPDATE,  'Изменение зависимости'),
        (ACTION_DEP_DELETE,  'Удаление зависимости'),
        (ACTION_DEP_ALIGN,   'Выравнивание дат'),
        (ACTION_CS_CREATE,   'Создание набора изменений'),
        (ACTION_CS_SUBMIT,   'Отправка на согласование'),
        (ACTION_CS_APPROVE,  'Утверждение набора изменений'),
        (ACTION_CS_REJECT,   'Отклонение набора изменений'),
        (ACTION_COMMENT_DELETE, 'Удаление комментария'),
    ]

    user       = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_logs', verbose_name='Пользователь',
    )
    action     = models.CharField('Действие', max_length=30, choices=ACTION_CHOICES)
    object_id  = models.PositiveIntegerField('ID объекта', null=True, blank=True)
    object_repr = models.CharField('Объект', max_length=500, blank=True)
    details    = models.JSONField('Детали', default=dict, blank=True)
    ip_address = models.GenericIPAddressField('IP-адрес', null=True, blank=True)
    created_at = models.DateTimeField('Время', auto_now_add=True)

    class Meta:
        db_table     = 'work_audit_log'
        verbose_name = 'Запись журнала'
        verbose_name_plural = 'Журнал аудита'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action']),
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'[{self.get_action_display()}] {self.object_repr} ({self.created_at})'


# ── Замечания и предложения ──────────────────────────────────────────────────

class Feedback(models.Model):
    """Замечания и предложения пользователей."""

    CATEGORY_FUNCTIONALITY = 'functionality'
    CATEGORY_LOGIC         = 'logic'
    CATEGORY_DESIGN        = 'design'
    CATEGORY_BUG           = 'bug'
    CATEGORY_OTHER         = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_FUNCTIONALITY, 'Функционал'),
        (CATEGORY_LOGIC,         'Логика / Алгоритмы'),
        (CATEGORY_DESIGN,        'Оформление'),
        (CATEGORY_BUG,           'Ошибка'),
        (CATEGORY_OTHER,         'Другое'),
    ]

    STATUS_NEW          = 'new'
    STATUS_ACCEPTED     = 'accepted'
    STATUS_IMPLEMENTED  = 'implemented'
    STATUS_REJECTED     = 'rejected'
    STATUS_CHOICES = [
        (STATUS_NEW,         'Новое'),
        (STATUS_ACCEPTED,    'Принято'),
        (STATUS_IMPLEMENTED, 'Выполнено'),
        (STATUS_REJECTED,    'Отклонено'),
    ]

    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                      related_name='feedbacks')
    category      = models.CharField(max_length=20, choices=CATEGORY_CHOICES,
                                      default=CATEGORY_OTHER, verbose_name='Категория')
    text          = models.TextField(verbose_name='Текст')
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                      default=STATUS_NEW, verbose_name='Статус')
    admin_comment = models.TextField(blank=True, default='', verbose_name='Комментарий администратора')
    screenshot    = models.ImageField(upload_to='feedback/', blank=True, null=True,
                                       verbose_name='Скриншот')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'work_feedback'
        verbose_name = 'Замечание / Предложение'
        verbose_name_plural = 'Замечания и предложения'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_category_display()}] {self.text[:50]}'


class FeedbackAttachment(models.Model):
    """Вложение (скриншот) к замечанию."""
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE,
                                  related_name='attachments')
    image    = models.ImageField(upload_to='feedback/', verbose_name='Изображение')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'work_feedback_attachment'
        ordering = ['created_at']

    def __str__(self):
        return f'Attachment #{self.pk} for Feedback #{self.feedback_id}'


# ── Песочница (Changeset) ────────────────────────────────────────────────────

class Changeset(models.Model):
    """
    Набор изменений (песочница).
    Подразделение собирает правки в changeset, затем отправляет
    на согласование. После утверждения изменения применяются атомарно.
    """

    STATUS_DRAFT    = 'draft'
    STATUS_REVIEW   = 'review'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_DRAFT,    'Черновик'),
        (STATUS_REVIEW,   'На согласовании'),
        (STATUS_APPROVED, 'Утверждён'),
        (STATUS_REJECTED, 'Отклонён'),
    ]

    pp_project = models.ForeignKey(
        PPProject, on_delete=models.CASCADE,
        related_name='changesets', verbose_name='Проект ПП',
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='changesets', verbose_name='Подразделение',
    )
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='authored_changesets', verbose_name='Автор',
    )
    title = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True, default='')
    status = models.CharField(
        'Статус', max_length=20,
        choices=STATUS_CHOICES, default=STATUS_DRAFT,
    )
    reject_comment = models.TextField(
        'Причина отклонения', blank=True, default='',
    )

    created_at   = models.DateTimeField('Создан', auto_now_add=True)
    updated_at   = models.DateTimeField('Обновлён', auto_now=True)
    submitted_at = models.DateTimeField('Отправлен', null=True, blank=True)
    reviewed_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_changesets', verbose_name='Рецензент',
    )
    reviewed_at  = models.DateTimeField('Дата рецензии', null=True, blank=True)
    published_at = models.DateTimeField('Дата применения', null=True, blank=True)

    class Meta:
        db_table = 'work_changeset'
        verbose_name = 'Набор изменений'
        verbose_name_plural = 'Наборы изменений'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['department']),
            models.Index(fields=['pp_project']),
        ]

    def __str__(self):
        return f'[{self.get_status_display()}] {self.title}'

    @property
    def items_count(self):
        return self.items.count()


class ChangesetItem(models.Model):
    """
    Отдельное изменение внутри набора.
    action='create' — новая строка (target_row=NULL, данные в field_changes).
    action='update' — правка существующей строки (diff в field_changes).
    action='delete' — удаление строки.
    """

    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Создание'),
        (ACTION_UPDATE, 'Изменение'),
        (ACTION_DELETE, 'Удаление'),
    ]

    changeset = models.ForeignKey(
        Changeset, on_delete=models.CASCADE,
        related_name='items', verbose_name='Набор изменений',
    )
    target_row = models.ForeignKey(
        Work, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='changeset_items', verbose_name='Строка ПП',
    )
    action = models.CharField(
        'Действие', max_length=10, choices=ACTION_CHOICES,
    )
    field_changes = models.JSONField(
        'Изменения полей', default=dict, blank=True,
        help_text='Для create: все поля новой строки. Для update: только изменённые поля.',
    )
    original_data = models.JSONField(
        'Исходные данные', default=dict, blank=True,
        help_text='Снимок оригинальных значений для обнаружения конфликтов.',
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        db_table = 'work_changeset_item'
        verbose_name = 'Элемент набора изменений'
        verbose_name_plural = 'Элементы набора изменений'
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['changeset']),
            models.Index(fields=['target_row']),
        ]

    def __str__(self):
        return f'{self.get_action_display()} #{self.target_row_id or "new"}'


# ── Комментарии к работе (Activity feed) ────────────────────────────────────

class WorkComment(models.Model):
    """Комментарий / запись активности к задаче (Work)."""

    work = models.ForeignKey(
        Work, on_delete=models.CASCADE,
        related_name='comments', verbose_name='Работа',
    )
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='work_comments', verbose_name='Автор',
    )
    text = models.TextField('Текст комментария')
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        db_table = 'work_comment'
        verbose_name = 'Комментарий к работе'
        verbose_name_plural = 'Комментарии к работам'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['work']),
        ]

    def __str__(self):
        return f'Комментарий #{self.pk} к работе #{self.work_id}'


# ── Уведомления пользователям ────────────────────────────────────────────────

class Notification(models.Model):
    """Уведомление пользователю."""
    TYPES = [
        ('info', 'Информация'),
        ('warning', 'Предупреждение'),
        ('success', 'Успех'),
        ('task', 'Задача'),
        ('overdue', 'Просрочка'),
        ('sandbox', 'Песочница'),
    ]
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPES, default='info')
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, default='')
    link = models.CharField(max_length=500, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} → {self.user}'
