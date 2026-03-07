"""
Модели приложения works.

Архитектура таблиц работ:
                    ┌─────────┐
                    │  Work   │  ← общая таблица работ
                    └────┬────┘
           ┌─────────────┴─────────────┐
           ▼                           ▼
      ┌──────────┐               ┌──────────┐
      │ TaskWork │  (план задач) │  PPWork  │  (производственный план)
      └──────────┘               └──────────┘

Запись в TaskWork или PPWork создаётся/обновляется при записи
в соответствующий модуль; Work хранит общие поля.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.employees.models import Employee, Department, Sector, NTCCenter

User = get_user_model()


# ── Универсальный справочник (аналог Flask directories) ───────────────────────

class Directory(models.Model):
    """
    Универсальная таблица справочников.
    Аналог Flask-таблицы directories с полями type, value, parent_id.
    Типы: center, position, dept, sector, executor, task_type, work_type, justification.
    """
    TYPE_CHOICES = [
        ('center',        'НТЦ-центр'),
        ('position',      'Должность'),
        ('dept',          'Отдел'),
        ('sector',        'Сектор'),
        ('executor',      'Исполнитель'),
        ('task_type',     'Тип работы'),
        ('work_type',     'Вид работы'),
        ('justification', 'Обоснование'),
        ('project',       'Проект'),
        ('milestone',     'Этап'),
        ('stage',         'Подэтап'),
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
    """
    Производственный план (аналог Flask pp_projects).
    Каждый план группирует строки ПП и может быть привязан к проекту УП.
    """
    name       = models.CharField('Название плана', max_length=255)
    directory  = models.ForeignKey(
        Directory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pp_projects', verbose_name='Связь со справочником',
    )
    # Привязка к проекту УП (модуль 1)
    up_project = models.ForeignKey(
        'Project', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pp_plans', verbose_name='Проект УП',
    )
    # Привязка к конкретному изделию проекта УП (опционально)
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


# ── Справочники работ ─────────────────────────────────────────────────────────

class Project(models.Model):
    """Проект (модуль Управления проектами)."""
    name_full  = models.CharField('Полное наименование', max_length=500)
    name_short = models.CharField('Краткое наименование', max_length=100, blank=True)
    # code сохраняем для совместимости, фактически = name_short
    code       = models.CharField('Шифр / код', max_length=100, blank=True)
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
    code       = models.CharField('Шифр',                 max_length=100, blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        db_table     = 'work_project_product'
        verbose_name = 'Изделие проекта'
        verbose_name_plural = 'Изделия проекта'
        ordering = ['name']

    def __str__(self):
        return f'{self.code} — {self.name}' if self.code else self.name


class WorkType(models.Model):
    """Тип работы (из справочника: Разработка, Выпуск документа…)."""
    name = models.CharField('Название', max_length=100, unique=True)

    class Meta:
        db_table     = 'work_type'
        verbose_name = 'Тип работы'
        verbose_name_plural = 'Типы работ'
        ordering = ['name']

    def __str__(self):
        return self.name


# ── Основная таблица работ ────────────────────────────────────────────────────

class Work(models.Model):
    """
    Универсальная запись о работе.
    Данные считываются из модулей ПО (план задач) и ПП (производственный план)
    и записываются обратно в них же.

    source_type указывает, из какого модуля пришла запись.
    """

    SOURCE_TASK = 'task'   # из плана задач (apps.works.TaskWork)
    SOURCE_PP   = 'pp'     # из производственного плана (apps.works.PPWork)

    SOURCE_CHOICES = [
        (SOURCE_TASK, 'План задач (ПО)'),
        (SOURCE_PP,   'Производственный план (ПП)'),
    ]

    # ── Источник ──────────────────────────────────────────────────────────
    source_type = models.CharField(
        'Источник', max_length=10, choices=SOURCE_CHOICES,
    )

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

    # ── Основные поля ─────────────────────────────────────────────────────
    work_type    = models.ForeignKey(
        WorkType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='works', verbose_name='Тип работы',
    )
    work_name    = models.CharField('Наименование работы', max_length=500)
    work_number  = models.CharField('Номер работы / документа', max_length=100, blank=True)
    description  = models.TextField('Описание / обоснование', blank=True)

    # ── Исполнитель ───────────────────────────────────────────────────────
    executor = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='works', verbose_name='Исполнитель',
    )
    # Имя текстом — если исполнитель не зарегистрирован в системе
    executor_name_raw = models.CharField(
        'Исполнитель (текст)', max_length=200, blank=True,
    )

    # ── Сроки ─────────────────────────────────────────────────────────────
    date_start = models.DateField('Начало работы', null=True, blank=True)
    date_end   = models.DateField('Конец работы',  null=True, blank=True)
    deadline   = models.DateField('Контрольный срок', null=True, blank=True)

    # ── Плановые часы по месяцам {«YYYY-MM»: hours} ───────────────────────
    plan_hours = models.JSONField(
        'Плановые часы (по месяцам)', default=dict, blank=True,
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
            models.Index(fields=['source_type']),
            models.Index(fields=['department']),
            models.Index(fields=['executor']),
            models.Index(fields=['date_start', 'date_end']),
            models.Index(fields=['source_type', 'deadline']),
            models.Index(fields=['deadline']),
        ]

    def __str__(self):
        return f'[{self.get_source_type_display()}] {self.work_name}'

    @property
    def total_plan_hours(self) -> float:
        """Сумма плановых часов по всем месяцам."""
        return sum(float(v) for v in self.plan_hours.values())


# ── Детали плана задач (ПО) ───────────────────────────────────────────────────

class TaskWork(models.Model):
    """
    Запись плана задач (аналог tasks из Flask-приложения).
    Связана с Work один-к-одному.
    """

    work  = models.OneToOneField(
        Work, on_delete=models.CASCADE,
        related_name='task_detail', verbose_name='Работа',
    )

    # ── Поля, специфичные для плана задач ─────────────────────────────────
    stage         = models.CharField('Стадия',         max_length=100, blank=True)
    justification = models.CharField('Основание',      max_length=500, blank=True)
    # Дополнительные исполнители с часами по месяцам [{name, hours:{...}}]
    executors_list = models.JSONField(
        'Список исполнителей', default=list, blank=True,
    )
    # Связанные строки производственного плана (JSON: список pp_id)
    actions = models.JSONField('Связи с ПП', default=dict, blank=True)

    # Отчётные документы хранятся в WorkReport

    class Meta:
        db_table     = 'work_task_work'
        verbose_name = 'Запись плана задач'
        verbose_name_plural = 'Записи плана задач'

    def __str__(self):
        return f'ПО: {self.work.work_name}'


# ── Множественные исполнители задачи ─────────────────────────────────────────

class TaskExecutor(models.Model):
    """
    Дополнительные исполнители задачи (аналог Flask task_executors).
    Каждый имеет своё распределение часов по месяцам.
    """
    work          = models.ForeignKey(
        Work, on_delete=models.CASCADE,
        related_name='task_executors', verbose_name='Работа',
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
        ]

    def __str__(self):
        return f'{self.executor_name} → {self.work.work_name}'


# ── Детали производственного плана (ПП) ──────────────────────────────────────

class PPWork(models.Model):
    """
    Запись производственного плана (аналог production_plan из Flask).
    Связана с Work один-к-одному.
    """

    work = models.OneToOneField(
        Work, on_delete=models.CASCADE,
        related_name='pp_detail', verbose_name='Работа',
    )

    # ── Коды и номера ─────────────────────────────────────────────────────
    row_code       = models.CharField('Код строки',   max_length=50,  blank=True)
    work_order     = models.CharField('Заказ-наряд',  max_length=100, blank=True)
    stage_num      = models.CharField('Этап',         max_length=50,  blank=True)
    milestone_num  = models.CharField('Подэтап',      max_length=50,  blank=True)
    work_num       = models.CharField('Номер работы', max_length=50,  blank=True)
    work_designation = models.CharField('Обозначение', max_length=200, blank=True)

    # ── Нормирование ─────────────────────────────────────────────────────
    # Количество листов А4
    sheets_a4 = models.DecimalField(
        'Листы А4', max_digits=8, decimal_places=2,
        null=True, blank=True,
    )
    norm = models.DecimalField(
        'Норма (чел.-ч)', max_digits=8, decimal_places=2,
        null=True, blank=True,
    )
    coeff = models.DecimalField(
        'Коэффициент', max_digits=5, decimal_places=3,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    # Итоговая трудоёмкость 2D и 3D
    total_2d = models.DecimalField(
        'Трудоёмкость 2D', max_digits=8, decimal_places=2,
        null=True, blank=True,
    )
    total_3d = models.DecimalField(
        'Трудоёмкость 3D', max_digits=8, decimal_places=2,
        null=True, blank=True,
    )
    labor = models.DecimalField(
        'Трудозатраты итого', max_digits=8, decimal_places=2,
        null=True, blank=True,
    )

    # ── Начальник сектора (текстом, т.к. может не совпадать с Employee) ──
    sector_head_name = models.CharField(
        'Начальник сектора', max_length=200, blank=True,
    )

    # ── Тип работы (текстом, как во Flask) ──────────────────────────────
    task_type = models.CharField(
        'Тип работы', max_length=100, blank=True,
        default='выпуск документа',
    )

    # ── Проект ПП ───────────────────────────────────────────────────────
    pp_project = models.ForeignKey(
        PPProject, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pp_works', verbose_name='Проект ПП',
    )

    # ── Аудит ───────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_pp_works', verbose_name='Создал',
    )

    class Meta:
        db_table     = 'work_pp_work'
        verbose_name = 'Запись производственного плана'
        verbose_name_plural = 'Записи производственного плана'
        indexes = [
            models.Index(fields=['work_order']),
            models.Index(fields=['row_code']),
        ]

    def __str__(self):
        return f'ПП: {self.work.work_name}'

    @property
    def computed_labor(self):
        """Расчётная трудоёмкость: norm * coeff (если не задана вручную)."""
        if self.labor is not None:
            return self.labor
        if self.norm is not None and self.coeff is not None:
            return self.norm * self.coeff
        return None


# ── Отчётные документы к работе ──────────────────────────────────────────────

class WorkReport(models.Model):
    """
    Выпущенный документ / акт по работе.
    Аналог таблицы reports из Flask-приложения.
    """

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
    inventory_num    = models.CharField('Инв. номер',              max_length=100, blank=True)
    date_accepted    = models.DateField('Дата сдачи', null=True, blank=True)
    doc_type         = models.CharField('Вид документа',  max_length=20,
                                        choices=DOC_TYPE_CHOICES, blank=True)
    doc_class        = models.CharField('Класс документа', max_length=20,
                                        choices=DOC_CLASS_CHOICES, blank=True)
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

    def __str__(self):
        return self.doc_name or f'Документ #{self.pk}'


# ── Журнал извещений ──────────────────────────────────────────────────────────

class Notice(models.Model):
    """Журнал корректирующих извещений."""

    STATUS_ACTIVE   = 'active'
    STATUS_CLOSED   = 'closed'
    STATUS_CHOICES  = [
        (STATUS_ACTIVE, 'Активно'),
        (STATUS_CLOSED, 'Закрыто'),
    ]

    notice_type  = models.CharField('Тип извещения', max_length=100, blank=True)
    department   = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notices', verbose_name='Отдел',
    )
    executor     = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notices', verbose_name='Исполнитель',
    )
    date_issued  = models.DateField('Дата выдачи', null=True, blank=True)
    subject      = models.CharField('Тема', max_length=500, blank=True)
    description  = models.TextField('Описание', blank=True)
    status       = models.CharField('Статус', max_length=10,
                                    choices=STATUS_CHOICES, default=STATUS_ACTIVE)
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
        ]

    def __str__(self):
        return f'[{self.status}] {self.subject or self.notice_type}'


# ── Производственный календарь ───────────────────────────────────────────────

class WorkCalendar(models.Model):
    """
    Норма рабочих часов для одного человека в календарном месяце.
    Используется в расчётах недозагрузки / перегрузки.
    """
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
        unique_together  = [('year', 'month')]
        ordering         = ['-year', 'month']

    def __str__(self):
        return f'{self.year}-{self.month:02d}: {self.hours_norm}ч'

    @property
    def month_key(self) -> str:
        """Ключ формата YYYY-MM для plan_hours."""
        return f'{self.year}-{self.month:02d}'


# ── Журнал действий пользователей ────────────────────────────────────────────

class AuditLog(models.Model):
    """
    Журнал действий пользователей для аудита.
    Фиксирует создание, изменение и удаление задач, синхронизацию ПП,
    смену ролей и другие важные события.
    """

    ACTION_TASK_CREATE   = 'task_create'
    ACTION_TASK_UPDATE   = 'task_update'
    ACTION_TASK_DELETE   = 'task_delete'
    ACTION_PP_SYNC       = 'pp_sync'
    ACTION_PP_CREATE     = 'pp_create'
    ACTION_PP_DELETE     = 'pp_delete'
    ACTION_ROLE_CHANGE   = 'role_change'
    ACTION_USER_CREATE   = 'user_create'
    ACTION_USER_DELETE   = 'user_delete'

    ACTION_CHOICES = [
        (ACTION_TASK_CREATE, 'Создание задачи'),
        (ACTION_TASK_UPDATE, 'Изменение задачи'),
        (ACTION_TASK_DELETE, 'Удаление задачи'),
        (ACTION_PP_SYNC,     'Синхронизация ПП'),
        (ACTION_PP_CREATE,   'Создание записи ПП'),
        (ACTION_PP_DELETE,   'Удаление записи ПП'),
        (ACTION_ROLE_CHANGE, 'Смена роли пользователя'),
        (ACTION_USER_CREATE, 'Создание пользователя'),
        (ACTION_USER_DELETE, 'Удаление пользователя'),
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
