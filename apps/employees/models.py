"""
Модели приложения employees.

Архитектура:
  Django User (auth)  ←── OneToOne ──→  Employee  (профиль сотрудника)
                                              │
                             ┌────────────────┼────────────────┐
                             ▼                ▼                ▼
                          Vacation          KPI          EmployeeDocument
"""
# Импорт стандартных инструментов Django ORM
from django.db import models
# Получение модели пользователя, определённой в настройках (AUTH_USER_MODEL)
from django.contrib.auth import get_user_model
# Валидаторы для ограничения диапазона числовых значений
from django.core.validators import MinValueValidator, MaxValueValidator

# Ссылка на активную модель пользователя (по умолчанию auth.User)
User = get_user_model()


# ── Справочники ──────────────────────────────────────────────────────────────

class Department(models.Model):
    """Отдел (подразделение)."""
    # Уникальный буквенно-цифровой код отдела (например, «110», «215А»)
    code       = models.CharField('Код отдела', max_length=20, unique=True)
    # Полное название отдела (необязательно — может оставаться пустым)
    name       = models.CharField('Название',   max_length=200, blank=True)
    # Принадлежность отдела к НТЦ-центру (SET_NULL — отдел не удаляется вместе с центром)
    ntc_center = models.ForeignKey(
        'NTCCenter', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='departments', verbose_name='НТЦ-центр',
    )

    class Meta:
        # Имя таблицы в БД
        db_table     = 'emp_department'
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'
        # Сортировка: сначала по НТЦ-центру, затем по коду отдела
        ordering = ['ntc_center', 'code']

    def __str__(self):
        # Если название задано — показываем «код — название», иначе только код
        return self.code if not self.name else f'{self.code} — {self.name}'


class Sector(models.Model):
    """Сектор внутри отдела."""
    # FK на родительский отдел; при удалении отдела все сектора удаляются каскадно
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE,
        related_name='sectors', verbose_name='Отдел',
    )
    # Код сектора (уникален в рамках отдела, например «1», «2А»)
    code = models.CharField('Код сектора', max_length=30)
    # Название сектора (необязательно)
    name = models.CharField('Название',   max_length=200, blank=True)

    class Meta:
        # Имя таблицы в БД
        db_table     = 'emp_sector'
        verbose_name = 'Сектор'
        verbose_name_plural = 'Секторы'
        # Пара (отдел, код) должна быть уникальной — код уникален внутри отдела
        unique_together = [('department', 'code')]
        # Сортировка: сначала по отделу, затем по коду сектора
        ordering = ['department', 'code']

    def __str__(self):
        # Строковое представление: «код отдела / код сектора»
        return f'{self.department.code} / {self.code}'


class NTCCenter(models.Model):
    """НТЦ-центр (НТЦ-1Ц, НТЦ-2Ц …)."""
    # Уникальный код НТЦ-центра (например, «НТЦ-1Ц», «НТЦ-2Ц»)
    code = models.CharField('Код НТЦ', max_length=20, unique=True)
    # Полное название НТЦ-центра (необязательно)
    name = models.CharField('Название', max_length=200, blank=True)

    class Meta:
        # Имя таблицы в БД
        db_table     = 'emp_ntc_center'
        verbose_name = 'НТЦ-центр'
        verbose_name_plural = 'НТЦ-центры'
        # Алфавитная сортировка по коду
        ordering = ['code']

    def __str__(self):
        # Строковое представление — код НТЦ-центра
        return self.code


# ── Основная модель сотрудника ───────────────────────────────────────────────

class Employee(models.Model):
    """
    Профиль сотрудника. Расширяет стандартного Django User.
    Все персональные данные, характеристики и принадлежность к подразделению.
    """

    # ── Роли ──────────────────────────────────────────────────────────────
    # Константы ролей — используются в коде вместо «магических строк»
    ROLE_ADMIN        = 'admin'        # полный доступ, управление пользователями
    ROLE_NTC_HEAD     = 'ntc_head'     # руководитель НТЦ-центра
    ROLE_NTC_DEPUTY   = 'ntc_deputy'   # заместитель руководителя НТЦ
    ROLE_DEPT_HEAD    = 'dept_head'    # начальник отдела
    ROLE_DEPT_DEPUTY  = 'dept_deputy'  # заместитель начальника отдела
    ROLE_SECTOR_HEAD  = 'sector_head'  # начальник сектора
    ROLE_USER         = 'user'         # рядовой исполнитель

    # Список допустимых значений поля role с человекочитаемыми названиями
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
    # Список должностей — используется для отображения в UI и фильтрации
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
    # OneToOne с auth.User: каждый пользователь имеет ровно один профиль Employee
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='employee', verbose_name='Учётная запись',
    )

    # ── ФИО ───────────────────────────────────────────────────────────────
    # Фамилия сотрудника (обязательное поле)
    last_name   = models.CharField('Фамилия',  max_length=100)
    # Имя сотрудника (обязательное поле)
    first_name  = models.CharField('Имя',      max_length=100)
    # Отчество (необязательно — может отсутствовать у иностранных граждан)
    patronymic  = models.CharField('Отчество', max_length=100, blank=True)

    # ── Должность и подразделение ─────────────────────────────────────────
    # Роль в системе — определяет права доступа и зону видимости данных
    role       = models.CharField('Роль',      max_length=20,
                                  choices=ROLE_CHOICES, default=ROLE_USER)
    # Должность по штатному расписанию
    position   = models.CharField('Должность', max_length=30,
                                  choices=POSITION_CHOICES, blank=True)
    # НТЦ-центр, к которому относится сотрудник (для фильтрации видимости)
    ntc_center = models.ForeignKey(
        NTCCenter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name='НТЦ-центр',
    )
    # Отдел, к которому относится сотрудник
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name='Отдел',
    )
    # Сектор внутри отдела (необязателен)
    sector = models.ForeignKey(
        Sector, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name='Сектор',
    )

    # ── Контактные данные ─────────────────────────────────────────────────
    # Рабочий или мобильный телефон сотрудника
    phone = models.CharField('Телефон',        max_length=30, blank=True)
    # Корпоративный email (используется для уведомлений)
    email_corp = models.EmailField('Корп. email', blank=True)

    # ── Параметры работы ─────────────────────────────────────────────────
    # Дата приёма на работу (для расчётов стажа и отпуска)
    hire_date     = models.DateField('Дата приёма', null=True, blank=True)
    # Дата увольнения (если заполнена — сотрудник считается уволенным)
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
    # Флаг «сменить пароль при следующем входе» (устанавливается администратором)
    must_change_password = models.BooleanField(
        'Сменить пароль при входе', default=False,
    )
    # Флаг активности сотрудника в системе (False — заблокирован)
    is_active = models.BooleanField('Активен', default=True)

    # ── Настройки интерфейса (JSON) ───────────────────────────────────────
    # Хранит ширины колонок таблиц и флаг show_all_depts (для ntc_head/ntc_deputy)
    col_settings = models.JSONField('Настройки колонок', default=dict, blank=True)

    # ── Аудит ─────────────────────────────────────────────────────────────
    # Дата и время создания профиля (заполняется автоматически)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    # Дата и время последнего изменения профиля (обновляется автоматически)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        # Имя таблицы в БД
        db_table     = 'emp_employee'
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        # Сортировка по алфавиту: фамилия, затем имя
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['department', 'role']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        # Строковое представление — полное ФИО сотрудника
        return self.full_name

    @property
    def full_name(self) -> str:
        """Фамилия Имя Отчество."""
        # Собираем список непустых частей ФИО
        parts = [self.last_name, self.first_name]
        # Добавляем отчество только если оно задано
        if self.patronymic:
            parts.append(self.patronymic)
        # Возвращаем строку через пробел
        return ' '.join(parts)

    @property
    def short_name(self) -> str:
        """Фамилия И.О."""
        # Берём первую букву имени с точкой (или пустую строку)
        fn = f'{self.first_name[:1]}.' if self.first_name else ''
        # Берём первую букву отчества с точкой (или пустую строку)
        pn = f'{self.patronymic[:1]}.' if self.patronymic else ''
        # Возвращаем «Фамилия И.О.» с удалением лишних пробелов
        return f'{self.last_name} {fn}{pn}'.strip()

    @property
    def effective_ntc_center(self):
        """НТЦ-центр сотрудника: прямой или унаследованный от отдела."""
        # Сначала проверяем прямую связь сотрудника с НТЦ
        if self.ntc_center_id:
            return self.ntc_center
        # Фолбэк: берём НТЦ отдела (актуально для dept_head / dept_deputy)
        if self.department_id and self.department.ntc_center_id:
            return self.department.ntc_center
        return None

    @property
    def is_writer(self) -> bool:
        """Имеет право создавать/редактировать записи."""
        # Все роли, кроме ROLE_USER, имеют право на запись
        return self.role in (
            self.ROLE_ADMIN, self.ROLE_NTC_HEAD, self.ROLE_NTC_DEPUTY,
            self.ROLE_DEPT_HEAD, self.ROLE_DEPT_DEPUTY, self.ROLE_SECTOR_HEAD,
        )


# ── Отпуска ──────────────────────────────────────────────────────────────────

class Vacation(models.Model):
    """Плановый/фактический отпуск сотрудника."""

    # Константы типов отсутствия — используются в коде
    TYPE_ANNUAL   = 'annual'  # ежегодный оплачиваемый отпуск
    TYPE_UNPAID   = 'unpaid'  # отпуск без сохранения зарплаты
    TYPE_SICK     = 'sick'    # больничный лист
    TYPE_OTHER    = 'other'   # иной вид отсутствия

    # Список допустимых типов отсутствия
    TYPE_CHOICES = [
        (TYPE_ANNUAL, 'Ежегодный оплачиваемый'),
        (TYPE_UNPAID, 'За свой счёт'),
        (TYPE_SICK,   'Больничный'),
        (TYPE_OTHER,  'Иное'),
    ]

    # FK на сотрудника; при удалении сотрудника все его отпуска удаляются
    employee   = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='vacations', verbose_name='Сотрудник',
    )
    # Тип отсутствия (ежегодный отпуск по умолчанию)
    vac_type   = models.CharField('Тип', max_length=10,
                                  choices=TYPE_CHOICES, default=TYPE_ANNUAL)
    # Дата начала периода отсутствия
    date_start = models.DateField('Начало')
    # Дата окончания периода отсутствия
    date_end   = models.DateField('Конец')
    # Произвольные примечания к записи об отпуске
    notes      = models.TextField('Примечания', blank=True)
    # Метка времени создания записи
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    # Метка времени последнего изменения
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        # Имя таблицы в БД
        db_table     = 'emp_vacation'
        verbose_name = 'Отпуск'
        verbose_name_plural = 'Отпуска'
        # Сортировка по дате начала (ближайшие первыми)
        ordering = ['date_start']
        indexes = [
            models.Index(fields=['employee', 'date_start']),
        ]

    def __str__(self):
        # Строковое представление: «Фамилия И.О.: дата_начала – дата_конца»
        return (f'{self.employee.short_name}: '
                f'{self.date_start} – {self.date_end}')

    @property
    def duration_days(self) -> int:
        # Количество дней включительно (конечная дата входит в период)
        return (self.date_end - self.date_start).days + 1


# ── KPI сотрудника ────────────────────────────────────────────────────────────

class KPI(models.Model):
    """Показатели эффективности сотрудника за период (месяц)."""

    # FK на сотрудника; при удалении сотрудника все KPI удаляются
    employee  = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='kpis', verbose_name='Сотрудник',
    )
    # Год, за который фиксируются показатели
    year  = models.PositiveSmallIntegerField('Год')
    # Месяц (1–12), за который фиксируются показатели
    month = models.PositiveSmallIntegerField(
        'Месяц',
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )

    # ── Трудоёмкость ─────────────────────────────────────────────────────
    # Плановые часы на месяц (из плана задач)
    plan_hours   = models.DecimalField('Плановые часы',
                                       max_digits=7, decimal_places=2, default=0)
    # Фактически отработанные/выполненные часы
    fact_hours   = models.DecimalField('Фактические часы',
                                       max_digits=7, decimal_places=2, default=0)
    # Выполнение плана, %  (0–200+)
    # Вычисляется автоматически в методе save()
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
    # Итоговый балл KPI (заполняется вручную или внешним расчётом)
    score = models.DecimalField('Итоговый балл KPI', max_digits=5,
                                decimal_places=2, null=True, blank=True)
    # Произвольные примечания к записи KPI
    notes = models.TextField('Примечания', blank=True)

    # Метка времени создания записи
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    # Метка времени последнего изменения
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        # Имя таблицы в БД
        db_table     = 'emp_kpi'
        verbose_name = 'KPI'
        verbose_name_plural = 'KPI'
        # На одного сотрудника — одна запись за год+месяц
        unique_together = [('employee', 'year', 'month')]
        # Сортировка: последние периоды первыми, внутри периода — по сотруднику
        ordering = ['-year', '-month', 'employee']

    def __str__(self):
        # Строковое представление: «Фамилия И.О. — YYYY/MM»
        return f'{self.employee.short_name} — {self.year}/{self.month:02d}'

    def save(self, *args, **kwargs):
        # Автоматический расчёт процента выполнения
        if self.plan_hours and self.plan_hours > 0:
            # Вычисляем процент с округлением до 2 знаков через Decimal.quantize
            self.completion_pct = (
                self.fact_hours / self.plan_hours * 100
            ).quantize(__import__('decimal').Decimal('0.01'))
        # Вызываем родительский save() для фактического сохранения в БД
        super().save(*args, **kwargs)


# ── Документы / характеристики сотрудника ────────────────────────────────────

class EmployeeDocument(models.Model):
    """Документы и характеристики, прикреплённые к сотруднику."""

    # Константы типов документов
    DOC_CHARACTERISTIC = 'characteristic'  # служебная характеристика
    DOC_ORDER          = 'order'            # приказ (о приёме, переводе и т.д.)
    DOC_CERTIFICATE    = 'certificate'      # удостоверение или сертификат
    DOC_OTHER          = 'other'            # прочие документы

    # Список допустимых типов документов
    DOC_TYPE_CHOICES = [
        (DOC_CHARACTERISTIC, 'Характеристика'),
        (DOC_ORDER,          'Приказ'),
        (DOC_CERTIFICATE,    'Удостоверение / сертификат'),
        (DOC_OTHER,          'Прочее'),
    ]

    # FK на сотрудника; при удалении сотрудника все документы удаляются
    employee  = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='documents', verbose_name='Сотрудник',
    )
    # Тип прикреплённого документа
    doc_type  = models.CharField('Тип документа', max_length=20,
                                 choices=DOC_TYPE_CHOICES, default=DOC_OTHER)
    # Название или заголовок документа
    title     = models.CharField('Название', max_length=255)
    # Дата документа (подписания, выдачи и т.п.)
    date      = models.DateField('Дата документа', null=True, blank=True)
    # Текстовое содержание документа или примечания
    notes     = models.TextField('Содержание / примечания', blank=True)
    # Метка времени создания записи в системе
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        # Имя таблицы в БД
        db_table     = 'emp_document'
        verbose_name = 'Документ сотрудника'
        verbose_name_plural = 'Документы сотрудников'
        # Последние по дате документы отображаются первыми
        ordering = ['-date']

    def __str__(self):
        # Строковое представление: «Фамилия И.О. — название документа»
        return f'{self.employee.short_name} — {self.title}'


# ── Делегирование прав ───────────────────────────────────────────────────────

class RoleDelegation(models.Model):
    """Временное делегирование зоны видимости от одного сотрудника другому."""

    # Константы типов зоны делегирования
    SCOPE_CENTER   = 'center'    # делегируется весь НТЦ-центр
    SCOPE_DEPT     = 'dept'      # делегируется один отдел
    SCOPE_SECTOR   = 'sector'    # делегируется один сектор
    SCOPE_EXECUTOR = 'executor'  # делегируется один исполнитель

    # Список допустимых типов зон делегирования
    SCOPE_CHOICES = [
        (SCOPE_CENTER,   'НТЦ-центр'),
        (SCOPE_DEPT,     'Отдел'),
        (SCOPE_SECTOR,   'Сектор'),
        (SCOPE_EXECUTOR, 'Исполнитель'),
    ]

    # Сотрудник, который делегирует свои права (делегатор)
    delegator = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='delegations_given', verbose_name='Делегирует',
    )
    # Сотрудник, который получает делегированные права (делегат)
    delegate = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='delegations_received', verbose_name='Получает',
    )
    # Тип зоны: что именно делегируется (центр / отдел / сектор / исполнитель)
    scope_type  = models.CharField('Тип зоны',    max_length=10, choices=SCOPE_CHOICES)
    # Значение зоны (код или идентификатор: например, код отдела «110»)
    scope_value = models.CharField('Значение',    max_length=100)
    # Флаг: True — делегируется право записи; False — только чтение
    can_write   = models.BooleanField('Право записи', default=False)
    # Дата и время окончания действия делегирования (после — автоматически неактивно)
    valid_until = models.DateTimeField('Действует до')
    # Метка времени создания записи о делегировании
    created_at  = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        # Имя таблицы в БД
        db_table     = 'emp_role_delegation'
        verbose_name = 'Делегирование прав'
        verbose_name_plural = 'Делегирования прав'
        # Последние созданные делегирования отображаются первыми
        ordering = ['-created_at']
        # Индекс для быстрого поиска активных делегирований по получателю и сроку
        indexes = [
            models.Index(fields=['delegate', 'valid_until']),
        ]
        # Ограничение: нельзя делегировать права самому себе
        constraints = [
            models.CheckConstraint(
                check=~models.Q(delegator=models.F('delegate')),
                name='chk_delegation_not_self',
            )
        ]

    def __str__(self):
        # Строковое представление: «делегатор → делегат [тип:значение]»
        return (f'{self.delegator.short_name} → {self.delegate.short_name}'
                f' [{self.scope_type}:{self.scope_value}]')
