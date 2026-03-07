"""
Модели приложения employees.

Архитектура:
  Django User (auth)  ←── OneToOne ──→  Employee  (профиль сотрудника)
                                              │
                             ┌────────────────┼────────────────┐
                             ▼                ▼                ▼
                          Vacation          KPI          EmployeeDocument
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


# ── Справочники ──────────────────────────────────────────────────────────────

class Department(models.Model):
    """Отдел (подразделение)."""
    code  = models.CharField('Код отдела',  max_length=20,  unique=True)
    name  = models.CharField('Название',    max_length=200, blank=True)

    class Meta:
        db_table     = 'emp_department'
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'
        ordering = ['code']

    def __str__(self):
        return self.code if not self.name else f'{self.code} — {self.name}'


class Sector(models.Model):
    """Сектор внутри отдела."""
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE,
        related_name='sectors', verbose_name='Отдел',
    )
    code = models.CharField('Код сектора', max_length=30)
    name = models.CharField('Название',   max_length=200, blank=True)

    class Meta:
        db_table     = 'emp_sector'
        verbose_name = 'Сектор'
        verbose_name_plural = 'Секторы'
        unique_together = [('department', 'code')]
        ordering = ['department', 'code']

    def __str__(self):
        return f'{self.department.code} / {self.code}'


class NTCCenter(models.Model):
    """НТЦ-центр (НТЦ-1Ц, НТЦ-2Ц …)."""
    code = models.CharField('Код НТЦ', max_length=20, unique=True)
    name = models.CharField('Название', max_length=200, blank=True)

    class Meta:
        db_table     = 'emp_ntc_center'
        verbose_name = 'НТЦ-центр'
        verbose_name_plural = 'НТЦ-центры'
        ordering = ['code']

    def __str__(self):
        return self.code


# ── Основная модель сотрудника ───────────────────────────────────────────────

class Employee(models.Model):
    """
    Профиль сотрудника. Расширяет стандартного Django User.
    Все персональные данные, характеристики и принадлежность к подразделению.
    """

    # ── Роли ──────────────────────────────────────────────────────────────
    ROLE_ADMIN        = 'admin'
    ROLE_NTC_HEAD     = 'ntc_head'
    ROLE_NTC_DEPUTY   = 'ntc_deputy'
    ROLE_DEPT_HEAD    = 'dept_head'
    ROLE_DEPT_DEPUTY  = 'dept_deputy'
    ROLE_SECTOR_HEAD  = 'sector_head'
    ROLE_USER         = 'user'

    ROLE_CHOICES = [
        (ROLE_ADMIN,       'Администратор'),
        (ROLE_NTC_HEAD,    'Руководитель НТЦ'),
        (ROLE_NTC_DEPUTY,  'Зам. руководителя НТЦ'),
        (ROLE_DEPT_HEAD,   'Начальник отдела'),
        (ROLE_DEPT_DEPUTY, 'Зам. начальника отдела'),
        (ROLE_SECTOR_HEAD, 'Начальник сектора'),
        (ROLE_USER,        'Исполнитель'),
    ]

    # ── Должности ─────────────────────────────────────────────────────────
    POSITION_CHOICES = [
        ('tech_3',              'Техник-конструктор'),
        ('tech_2',              'Техник-конструктор 2 кат.'),
        ('tech_1',              'Техник-конструктор 1 кат.'),
        ('spec',                'Специалист'),
        ('spec_2',              'Специалист 2 кат.'),
        ('spec_1',              'Специалист 1 кат.'),
        ('eng',                 'Инженер-конструктор'),
        ('eng_3',               'Инженер-конструктор 3 кат.'),
        ('eng_2',               'Инженер-конструктор 2 кат.'),
        ('eng_1',               'Инженер-конструктор 1 кат.'),
        ('lead_eng',            'Ведущий инженер-конструктор'),
        ('sector_head',         'Начальник сектора'),
        ('dept_deputy_sector',  'Зам. начальника отдела – начальник сектора'),
        ('dept_deputy',         'Зам. начальника отдела'),
        ('dept_head',           'Начальник отдела'),
        ('dir_direction',       'Руководитель направления'),
        ('ntc_deputy',          'Зам. руководителя НТЦ'),
        ('ntc_head',            'Руководитель НТЦ'),
    ]

    # ── Связь с User ──────────────────────────────────────────────────────
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='employee', verbose_name='Учётная запись',
    )

    # ── ФИО ───────────────────────────────────────────────────────────────
    last_name   = models.CharField('Фамилия',  max_length=100)
    first_name  = models.CharField('Имя',      max_length=100)
    patronymic  = models.CharField('Отчество', max_length=100, blank=True)

    # ── Должность и подразделение ─────────────────────────────────────────
    role       = models.CharField('Роль',      max_length=20,
                                  choices=ROLE_CHOICES, default=ROLE_USER)
    position   = models.CharField('Должность', max_length=30,
                                  choices=POSITION_CHOICES, blank=True)
    ntc_center = models.ForeignKey(
        NTCCenter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name='НТЦ-центр',
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name='Отдел',
    )
    sector = models.ForeignKey(
        Sector, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name='Сектор',
    )

    # ── Контактные данные ─────────────────────────────────────────────────
    phone = models.CharField('Телефон',        max_length=30, blank=True)
    email_corp = models.EmailField('Корп. email', blank=True)

    # ── Параметры работы ─────────────────────────────────────────────────
    hire_date     = models.DateField('Дата приёма', null=True, blank=True)
    dismissal_date = models.DateField('Дата увольнения', null=True, blank=True)
    # Норма часов в месяц (по умолчанию 168 — стандарт РФ)
    monthly_hours_norm = models.PositiveSmallIntegerField(
        'Норма часов/мес', default=168,
    )
    # Коэффициент для расчёта трудоёмкости (индивидуальный, 0.5–2.0)
    personal_coeff = models.DecimalField(
        'Личный коэффициент', max_digits=4, decimal_places=2,
        default=1.00,
        validators=[MinValueValidator(0.1), MaxValueValidator(5.0)],
    )

    # ── Флаги ─────────────────────────────────────────────────────────────
    must_change_password = models.BooleanField(
        'Сменить пароль при входе', default=False,
    )
    is_active = models.BooleanField('Активен', default=True)

    # ── Настройки интерфейса (JSON) ───────────────────────────────────────
    col_settings = models.JSONField('Настройки колонок', default=dict, blank=True)

    # ── Аудит ─────────────────────────────────────────────────────────────
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        db_table     = 'emp_employee'
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return self.full_name

    @property
    def full_name(self) -> str:
        """Фамилия Имя Отчество."""
        parts = [self.last_name, self.first_name]
        if self.patronymic:
            parts.append(self.patronymic)
        return ' '.join(parts)

    @property
    def short_name(self) -> str:
        """Фамилия И.О."""
        fn = f'{self.first_name[:1]}.' if self.first_name else ''
        pn = f'{self.patronymic[:1]}.' if self.patronymic else ''
        return f'{self.last_name} {fn}{pn}'.strip()

    @property
    def is_writer(self) -> bool:
        """Имеет право создавать/редактировать записи."""
        return self.role in (
            self.ROLE_ADMIN, self.ROLE_NTC_HEAD, self.ROLE_NTC_DEPUTY,
            self.ROLE_DEPT_HEAD, self.ROLE_DEPT_DEPUTY, self.ROLE_SECTOR_HEAD,
        )


# ── Отпуска ──────────────────────────────────────────────────────────────────

class Vacation(models.Model):
    """Плановый/фактический отпуск сотрудника."""

    TYPE_ANNUAL   = 'annual'
    TYPE_UNPAID   = 'unpaid'
    TYPE_SICK     = 'sick'
    TYPE_OTHER    = 'other'

    TYPE_CHOICES = [
        (TYPE_ANNUAL, 'Ежегодный оплачиваемый'),
        (TYPE_UNPAID, 'За свой счёт'),
        (TYPE_SICK,   'Больничный'),
        (TYPE_OTHER,  'Иное'),
    ]

    employee   = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='vacations', verbose_name='Сотрудник',
    )
    vac_type   = models.CharField('Тип', max_length=10,
                                  choices=TYPE_CHOICES, default=TYPE_ANNUAL)
    date_start = models.DateField('Начало')
    date_end   = models.DateField('Конец')
    notes      = models.TextField('Примечания', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        db_table     = 'emp_vacation'
        verbose_name = 'Отпуск'
        verbose_name_plural = 'Отпуска'
        ordering = ['date_start']

    def __str__(self):
        return (f'{self.employee.short_name}: '
                f'{self.date_start} – {self.date_end}')

    @property
    def duration_days(self) -> int:
        return (self.date_end - self.date_start).days + 1


# ── KPI сотрудника ────────────────────────────────────────────────────────────

class KPI(models.Model):
    """Показатели эффективности сотрудника за период (месяц)."""

    employee  = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='kpis', verbose_name='Сотрудник',
    )
    year  = models.PositiveSmallIntegerField('Год')
    month = models.PositiveSmallIntegerField(
        'Месяц',
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )

    # ── Трудоёмкость ─────────────────────────────────────────────────────
    plan_hours   = models.DecimalField('Плановые часы',
                                       max_digits=7, decimal_places=2, default=0)
    fact_hours   = models.DecimalField('Фактические часы',
                                       max_digits=7, decimal_places=2, default=0)
    # Выполнение плана, %  (0–200+)
    completion_pct = models.DecimalField('Выполнение плана, %',
                                         max_digits=6, decimal_places=2,
                                         null=True, blank=True)

    # ── Качество ─────────────────────────────────────────────────────────
    # Количество замечаний нормоконтроля
    norm_control_remarks = models.PositiveSmallIntegerField(
        'Замечания нормоконтроля', default=0,
    )
    # Количество выпущенных документов
    docs_issued = models.PositiveSmallIntegerField('Выпущено документов', default=0)

    # ── Итоговый балл KPI (рассчитывается внешней логикой) ───────────────
    score = models.DecimalField('Итоговый балл KPI', max_digits=5,
                                decimal_places=2, null=True, blank=True)
    notes = models.TextField('Примечания', blank=True)

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        db_table     = 'emp_kpi'
        verbose_name = 'KPI'
        verbose_name_plural = 'KPI'
        unique_together = [('employee', 'year', 'month')]
        ordering = ['-year', '-month', 'employee']

    def __str__(self):
        return f'{self.employee.short_name} — {self.year}/{self.month:02d}'

    def save(self, *args, **kwargs):
        # Автоматический расчёт процента выполнения
        if self.plan_hours and self.plan_hours > 0:
            self.completion_pct = (
                self.fact_hours / self.plan_hours * 100
            ).quantize(__import__('decimal').Decimal('0.01'))
        super().save(*args, **kwargs)


# ── Документы / характеристики сотрудника ────────────────────────────────────

class EmployeeDocument(models.Model):
    """Документы и характеристики, прикреплённые к сотруднику."""

    DOC_CHARACTERISTIC = 'characteristic'
    DOC_ORDER          = 'order'
    DOC_CERTIFICATE    = 'certificate'
    DOC_OTHER          = 'other'

    DOC_TYPE_CHOICES = [
        (DOC_CHARACTERISTIC, 'Характеристика'),
        (DOC_ORDER,          'Приказ'),
        (DOC_CERTIFICATE,    'Удостоверение / сертификат'),
        (DOC_OTHER,          'Прочее'),
    ]

    employee  = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='documents', verbose_name='Сотрудник',
    )
    doc_type  = models.CharField('Тип документа', max_length=20,
                                 choices=DOC_TYPE_CHOICES, default=DOC_OTHER)
    title     = models.CharField('Название', max_length=255)
    date      = models.DateField('Дата документа', null=True, blank=True)
    notes     = models.TextField('Содержание / примечания', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        db_table     = 'emp_document'
        verbose_name = 'Документ сотрудника'
        verbose_name_plural = 'Документы сотрудников'
        ordering = ['-date']

    def __str__(self):
        return f'{self.employee.short_name} — {self.title}'


# ── Делегирование прав ───────────────────────────────────────────────────────

class RoleDelegation(models.Model):
    """Временное делегирование зоны видимости от одного сотрудника другому."""

    SCOPE_CENTER   = 'center'
    SCOPE_DEPT     = 'dept'
    SCOPE_SECTOR   = 'sector'
    SCOPE_EXECUTOR = 'executor'

    SCOPE_CHOICES = [
        (SCOPE_CENTER,   'НТЦ-центр'),
        (SCOPE_DEPT,     'Отдел'),
        (SCOPE_SECTOR,   'Сектор'),
        (SCOPE_EXECUTOR, 'Исполнитель'),
    ]

    delegator = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='delegations_given', verbose_name='Делегирует',
    )
    delegate = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='delegations_received', verbose_name='Получает',
    )
    scope_type  = models.CharField('Тип зоны',    max_length=10, choices=SCOPE_CHOICES)
    scope_value = models.CharField('Значение',    max_length=100)
    can_write   = models.BooleanField('Право записи', default=False)
    valid_until = models.DateTimeField('Действует до')
    created_at  = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        db_table     = 'emp_role_delegation'
        verbose_name = 'Делегирование прав'
        verbose_name_plural = 'Делегирования прав'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['delegate', 'valid_until']),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(delegator=models.F('delegate')),
                name='chk_delegation_not_self',
            )
        ]

    def __str__(self):
        return (f'{self.delegator.short_name} → {self.delegate.short_name}'
                f' [{self.scope_type}:{self.scope_value}]')
