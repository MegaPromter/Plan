"""
Утилиты для API: фильтрация по ролям, нормализация данных.
Аналог Flask-хелперов: _get_visibility_filter, _norm_plan_hours и т.д.
"""
# Стандартный модуль JSON (используется при парсинге строк в dict)
import json
# calendar — для вычисления последнего дня месяца
import calendar
# date и timedelta из стандартной библиотеки
from datetime import date, timedelta
# Decimal — для точных вычислений с дробными числами (финансовые данные)
from decimal import Decimal

# Q — объект для построения сложных ORM-запросов (OR/AND)
from django.db.models import Q
# timezone — работа со временем с учётом часового пояса
from django.utils import timezone

# Модели сотрудников: Employee (профиль) и RoleDelegation (делегирования)
from apps.employees.models import Employee, RoleDelegation


# ── Роли и константы ──────────────────────────────────────────────────────────

# Все допустимые значения поля role у Employee
VALID_ROLES = {
    'admin', 'ntc_head', 'ntc_deputy',
    'dept_head', 'dept_deputy', 'sector_head', 'user',
}

# Роли, которым разрешено создавать/изменять данные (не read-only)
WRITER_ROLES = {
    'admin', 'ntc_head', 'ntc_deputy',
    'dept_head', 'dept_deputy', 'sector_head',
}

# Словарь: код роли → читаемое название на русском
ROLE_LABELS = {
    'admin':       'Администратор',
    'ntc_head':    'Руководитель НТЦ',
    'ntc_deputy':  'Зам. руководителя НТЦ',
    'dept_head':   'Начальник отдела',
    'dept_deputy': 'Зам. начальника отдела',
    'sector_head': 'Начальник сектора',
    'user':        'Исполнитель',
}

# Поля, разрешённые для inline-обновления (production_plan)
# Только эти поля можно обновлять через PUT ?field=... в ПП
PRODUCTION_ALLOWED_FIELDS = {
    'row_code', 'work_order', 'stage_num', 'milestone_num',
    'work_num', 'work_designation', 'work_name',
    'date_start', 'date_end', 'sheets_a4', 'norm', 'coeff',
    'total_2d', 'total_3d', 'labor', 'center', 'dept',
    'sector_head', 'executor', 'task_type',
}

# Поля, разрешённые для inline-обновления (vacations)
# Только эти поля можно менять через PUT в модуле отпусков
VACATION_ALLOWED_FIELDS = {
    'executor', 'date_start', 'date_end', 'notes',
}


# ── IP-адрес клиента ──────────────────────────────────────────────────────────

def get_client_ip(request):
    """Возвращает IP-адрес клиента из REMOTE_ADDR.
    X-Forwarded-For не используется — легко подделать."""
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


# ── Фильтрация по ролям (visibility) ──────────────────────────────────────────

def get_visibility_filter(user):
    """
    Возвращает Q-объект для фильтрации Work/TaskWork по роли пользователя.
    Аналог Flask _get_visibility_filter().

    Работает через связи Django ORM:
    - Work.ntc_center, Work.department, Work.sector, Work.executor
    """
    # Получаем профиль Employee для данного пользователя (None если нет профиля)
    employee = getattr(user, 'employee', None)
    if not employee:
        # Нет профиля — не показываем ничего (пустой queryset через невалидный фильтр)
        return Q(pk__isnull=True)  # Ничего не показываем

    # Текущая роль сотрудника
    role = employee.role
    # Текущий момент времени для проверки срока делегирований
    now = timezone.now()

    if role == 'admin':
        return Q()  # Без фильтра — видит всё

    # show_all_depts: руководители НТЦ могут включить видимость всех подразделений
    # Читаем из col_settings (JSONField, хранит пользовательские настройки)
    col_settings = employee.col_settings or {}
    if role in ('ntc_head', 'ntc_deputy') and col_settings.get('show_all_depts'):
        return Q()  # Видит всё (как admin)

    # Базовый фильтр по роли
    q = Q()
    if role in ('ntc_head', 'ntc_deputy'):
        # Руководитель НТЦ видит только свой центр
        if employee.ntc_center:
            q = Q(ntc_center=employee.ntc_center)
        else:
            # Центр не назначен — ничего не показываем
            q = Q(pk__isnull=True)
    elif role in ('dept_head', 'dept_deputy'):
        # Начальник отдела видит только свой отдел
        if employee.department:
            q = Q(department=employee.department)
        else:
            # Отдел не назначен — ничего не показываем
            q = Q(pk__isnull=True)
    elif role == 'sector_head':
        # Начальник сектора видит только свой сектор
        if employee.department and employee.sector:
            # Оба поля заполнены — фильтруем по отделу И сектору
            q = Q(department=employee.department, sector=employee.sector)
        else:
            # Сектор или отдел не назначен — ничего не показываем
            # (sector_head без привязки к сектору не должен видеть весь отдел)
            q = Q(pk__isnull=True)
    else:
        # user — видит задачи своего отдела (как dept_head)
        if employee.department:
            q = Q(department=employee.department)
        else:
            # Отдел не назначен — видит только свои задачи
            q = Q(executor=employee) | Q(created_by=employee)

    # Добавляем делегирования: временно расширяем видимость на чужие данные
    delegations = RoleDelegation.objects.filter(
        delegate=employee,   # делегирование адресовано именно этому сотруднику
        valid_until__gt=now, # ещё действует (не истёк срок)
    )
    for d in delegations:
        # Расширяем фильтр в зависимости от типа области делегирования
        if d.scope_type == 'center':
            # Делегирование по НТЦ-центру
            q = q | Q(ntc_center__code=d.scope_value)
        elif d.scope_type == 'dept':
            # Делегирование по отделу
            q = q | Q(department__code=d.scope_value)
        elif d.scope_type == 'sector':
            # Делегирование по сектору
            q = q | Q(sector__code=d.scope_value)
        elif d.scope_type == 'executor':
            # Делегирование по конкретному исполнителю (по фамилии через FK)
            q = q | Q(executor__last_name__icontains=d.scope_value)

    return q


def get_vacation_visibility_filter(user):
    """
    Возвращает Q-объект для фильтрации Vacation по роли пользователя.
    Vacations привязаны к Employee, не к Work — другая логика.
    """
    # Получаем профиль Employee
    employee = getattr(user, 'employee', None)
    if not employee:
        # Нет профиля — ничего не показываем
        return Q(pk__isnull=True)

    # Роль сотрудника
    role = employee.role
    # Текущее время для проверки делегирований
    now = timezone.now()

    if role == 'admin':
        # Администратор видит все отпуска
        return Q()

    # Базовый Q-фильтр (заполняется ниже в зависимости от роли)
    q = Q()
    if role in ('ntc_head', 'ntc_deputy'):
        # Руководитель НТЦ — видит отпуска сотрудников своего центра
        if employee.ntc_center:
            q = Q(employee__ntc_center=employee.ntc_center)
        else:
            q = Q(pk__isnull=True)
    elif role in ('dept_head', 'dept_deputy'):
        # Начальник отдела — видит отпуска своего отдела
        if employee.department:
            q = Q(employee__department=employee.department)
        else:
            q = Q(pk__isnull=True)
    elif role == 'sector_head':
        # Начальник сектора — видит отпуска только своего сектора
        if employee.department and employee.sector:
            q = Q(
                employee__department=employee.department,
                employee__sector=employee.sector,
            )
        else:
            # Сектор или отдел не назначен — ничего не показываем
            q = Q(pk__isnull=True)
    else:
        # Обычный пользователь — видит только свои отпуска
        q = Q(employee=employee)

    # Делегирования — расширяем видимость отпусков
    delegations = RoleDelegation.objects.filter(
        delegate=employee,   # адресовано данному сотруднику
        valid_until__gt=now, # действует
    )
    for d in delegations:
        if d.scope_type == 'center':
            # Видит отпуска сотрудников центра
            q = q | Q(employee__ntc_center__code=d.scope_value)
        elif d.scope_type == 'dept':
            # Видит отпуска сотрудников отдела
            q = q | Q(employee__department__code=d.scope_value)
        elif d.scope_type == 'sector':
            # Видит отпуска сотрудников сектора
            q = q | Q(employee__sector__code=d.scope_value)
        elif d.scope_type == 'executor':
            # Видит отпуска конкретного сотрудника (по фамилии)
            q = q | Q(employee__last_name__icontains=d.scope_value)

    return q


# ── Нормализация и валидация plan_hours ─────────────────────────────────────

# Ленивый импорт re (regex) с псевдонимом во избежание конфликта имён
import re as _re

# Регулярное выражение для проверки ключей plan_hours: формат 'YYYY-MM'
_MONTH_KEY_RE = _re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')


def validate_plan_hours(ph) -> tuple[dict, str | None]:
    """
    Валидирует и нормализует plan_hours.
    Возвращает (clean_dict, error_message).
    error_message is None если нет ошибки.

    Правила:
      - Ключи должны быть формата 'YYYY-MM'
      - Значения должны быть неотрицательными числами
      - Максимум 60 записей (5 лет по месяцам)
    """
    if ph is None:
        # None считается допустимым (нет данных) — возвращаем пустой dict
        return {}, None
    if isinstance(ph, str):
        # Если пришла строка — пытаемся разобрать как JSON
        try:
            ph = json.loads(ph)
        except (json.JSONDecodeError, ValueError):
            return {}, 'plan_hours: невалидный JSON'
    if not isinstance(ph, dict):
        # plan_hours должен быть объектом (dict), а не массивом или числом
        return {}, 'plan_hours: ожидается объект'
    if len(ph) > 60:
        # Ограничение: не более 60 месяцев (~5 лет)
        return {}, 'plan_hours: слишком много записей (максимум 60)'
    # Словарь для очищенных данных
    clean = {}
    for k, v in ph.items():
        # Проверяем формат ключа (YYYY-MM)
        if not isinstance(k, str) or not _MONTH_KEY_RE.match(k):
            return {}, f'plan_hours: невалидный ключ "{k}" (ожидается YYYY-MM)'
        try:
            # Конвертируем значение в float
            fv = float(v)
        except (TypeError, ValueError):
            return {}, f'plan_hours: невалидное значение для ключа "{k}"'
        if fv < 0:
            # Отрицательные часы недопустимы
            return {}, f'plan_hours: отрицательное значение для ключа "{k}"'
        # Сохраняем все значения включая 0 — явный 0 означает сброс часов;
        # клиент может проверять наличие ключа в словаре
        clean[k] = fv
    return clean, None


def validate_executors_list(el) -> tuple[list, str | None]:
    """
    Валидирует executors_list.
    Каждый элемент: {'name': str, 'hours': {YYYY-MM: float}}.
    Возвращает (clean_list, error_message).
    """
    if el is None:
        # Нет данных — допустимо
        return [], None
    if isinstance(el, str):
        # Пришла строка — парсим JSON
        try:
            el = json.loads(el)
        except (json.JSONDecodeError, ValueError):
            return [], 'executors_list: невалидный JSON'
    if not isinstance(el, list):
        # Должен быть массив объектов
        return [], 'executors_list: ожидается массив'
    if len(el) > 50:
        # Ограничение: не более 50 исполнителей на задачу
        return [], 'executors_list: слишком много исполнителей (максимум 50)'
    clean = []
    for i, item in enumerate(el):
        if not isinstance(item, dict):
            # Каждый элемент должен быть объектом
            return [], f'executors_list[{i}]: ожидается объект'
        # Имя исполнителя: обязательное поле, обрезаем пробелы
        name = str(item.get('name', '')).strip()
        if not name:
            return [], f'executors_list[{i}]: имя исполнителя обязательно'
        # Валидируем вложенный plan_hours исполнителя
        hours, err = validate_plan_hours(item.get('hours'))
        if err:
            return [], f'executors_list[{i}].hours: {err}'
        clean.append({'name': name, 'hours': hours})
    return clean, None


def validate_actions(actions) -> tuple[dict, str | None]:
    """
    Валидирует поле actions (TaskWork).
    Ожидается dict или None.
    """
    if actions is None:
        # None — допустимо, возвращаем пустой dict
        return {}, None
    if isinstance(actions, str):
        # Пришла строка — пытаемся разобрать как JSON
        try:
            actions = json.loads(actions)
        except (json.JSONDecodeError, ValueError):
            return {}, 'actions: невалидный JSON'
    if not isinstance(actions, dict):
        # actions должен быть объектом (dict)
        return {}, 'actions: ожидается объект'
    # actions валиден — возвращаем как есть
    return actions, None


def norm_plan_hours(ph):
    """
    Нормализация plan_hours. Аналог Flask _norm_plan_hours().
    Принимает dict или str, возвращает dict.
    """
    if ph is None:
        # Нет данных — пустой словарь
        return {}
    if isinstance(ph, str):
        # Строка — десериализуем JSON
        try:
            ph = json.loads(ph)
        except (json.JSONDecodeError, ValueError):
            return {}
    if isinstance(ph, dict):
        # Конвертируем все значения в float, исключая нулевые
        return {k: float(v) for k, v in ph.items() if v}
    return {}


def parse_json_hours(raw):
    """Безопасный парсинг JSON plan_hours."""
    if raw is None:
        # Нет значения — пустой словарь
        return {}
    if isinstance(raw, dict):
        # Уже dict — возвращаем как есть
        return raw
    if isinstance(raw, str):
        # Строка — пробуем разобрать JSON
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


# ── MCC Finish (закрытие задачи в конце месяца) ──────────────────────────────

def mcc_finish_data():
    """
    Возвращает (last_day_prev_month, cutoff_key) для закрытия задачи.
    Аналог Flask _mcc_finish логики.
    """
    # Сегодняшняя дата
    today = date.today()
    if today.month == 1:
        # Январь — предыдущий месяц это декабрь прошлого года
        last_day = date(today.year - 1, 12, 31)
    else:
        # Вычисляем последний день предыдущего месяца
        last_day = date(
            today.year, today.month - 1,
            calendar.monthrange(today.year, today.month - 1)[1]  # [1] = кол-во дней
        )
    # Ключ-граница для plan_hours: 'YYYY-MM' текущего месяца
    # Все записи с ключом < cutoff остаются, ключи >= cutoff удаляются
    cutoff = f"{today.year}-{str(today.month).zfill(2)}"
    return last_day, cutoff


# ── JSON-сериализация моделей ────────────────────────────────────────────────

class DecimalEncoder(json.JSONEncoder):
    """JSON-энкодер, обрабатывающий Decimal."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            # Конвертируем Decimal в float для JSON-сериализации
            return float(obj)
        if isinstance(obj, date):
            # Конвертируем date в строку ISO 8601 ('YYYY-MM-DD')
            return obj.isoformat()
        # Для остальных типов используем стандартный энкодер
        return super().default(obj)


def model_to_dict_json(instance, fields=None, exclude=None):
    """Конвертация модели в dict для JSON-ответа."""
    # Используем встроенную Django-функцию model_to_dict
    from django.forms.models import model_to_dict
    d = model_to_dict(instance, fields=fields, exclude=exclude)
    # Конвертируем типы, несовместимые с JSON
    for k, v in d.items():
        if isinstance(v, Decimal):
            # Decimal → float
            d[k] = float(v)
        elif isinstance(v, date):
            # date → строка ISO 8601
            d[k] = v.isoformat()
    return d
