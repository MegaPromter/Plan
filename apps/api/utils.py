"""
Утилиты для API: фильтрация по ролям, нормализация данных.
Аналог Flask-хелперов: _get_visibility_filter, _norm_plan_hours и т.д.
"""
import json
import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.employees.models import Employee, RoleDelegation


# ── Роли и константы ──────────────────────────────────────────────────────────

VALID_ROLES = {
    'admin', 'ntc_head', 'ntc_deputy',
    'dept_head', 'dept_deputy', 'sector_head', 'user',
}

WRITER_ROLES = {
    'admin', 'ntc_head', 'ntc_deputy',
    'dept_head', 'dept_deputy', 'sector_head',
}

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
PRODUCTION_ALLOWED_FIELDS = {
    'row_code', 'work_order', 'stage_num', 'milestone_num',
    'work_num', 'work_designation', 'work_name',
    'date_start', 'date_end', 'sheets_a4', 'norm', 'coeff',
    'total_2d', 'total_3d', 'labor', 'center', 'dept',
    'sector_head', 'executor', 'task_type',
}

# Поля, разрешённые для inline-обновления (vacations)
VACATION_ALLOWED_FIELDS = {
    'executor', 'date_start', 'date_end', 'notes',
}


# ── Фильтрация по ролям (visibility) ──────────────────────────────────────────

def get_visibility_filter(user):
    """
    Возвращает Q-объект для фильтрации Work/TaskWork по роли пользователя.
    Аналог Flask _get_visibility_filter().

    Работает через связи Django ORM:
    - Work.ntc_center, Work.department, Work.sector, Work.executor
    """
    employee = getattr(user, 'employee', None)
    if not employee:
        return Q(pk__isnull=True)  # Ничего не показываем

    role = employee.role
    now = timezone.now()

    if role == 'admin':
        return Q()  # Без фильтра — видит всё

    # show_all_depts: руководители НТЦ могут включить видимость всех подразделений
    col_settings = employee.col_settings or {}
    if role in ('ntc_head', 'ntc_deputy') and col_settings.get('show_all_depts'):
        return Q()  # Видит всё (как admin)

    # Базовый фильтр по роли
    q = Q()
    if role in ('ntc_head', 'ntc_deputy'):
        if employee.ntc_center:
            q = Q(ntc_center=employee.ntc_center)
        else:
            q = Q(pk__isnull=True)
    elif role in ('dept_head', 'dept_deputy'):
        if employee.department:
            q = Q(department=employee.department)
        else:
            q = Q(pk__isnull=True)
    elif role == 'sector_head':
        if employee.department and employee.sector:
            q = Q(department=employee.department, sector=employee.sector)
        elif employee.department:
            q = Q(department=employee.department)
        else:
            q = Q(pk__isnull=True)
    else:
        # user — видит только свои задачи
        q = Q(executor=employee) | Q(created_by=employee)
        q = q | Q(executor_name_raw__icontains=employee.last_name)

    # Добавляем делегирования
    delegations = RoleDelegation.objects.filter(
        delegate=employee,
        valid_until__gt=now,
    )
    for d in delegations:
        if d.scope_type == 'center':
            q = q | Q(ntc_center__code=d.scope_value)
        elif d.scope_type == 'dept':
            q = q | Q(department__code=d.scope_value)
        elif d.scope_type == 'sector':
            q = q | Q(sector__code=d.scope_value)
        elif d.scope_type == 'executor':
            q = q | Q(executor_name_raw__icontains=d.scope_value)

    return q


def get_vacation_visibility_filter(user):
    """
    Возвращает Q-объект для фильтрации Vacation по роли пользователя.
    Vacations привязаны к Employee, не к Work — другая логика.
    """
    employee = getattr(user, 'employee', None)
    if not employee:
        return Q(pk__isnull=True)

    role = employee.role
    now = timezone.now()

    if role == 'admin':
        return Q()

    q = Q()
    if role in ('ntc_head', 'ntc_deputy'):
        if employee.ntc_center:
            q = Q(employee__ntc_center=employee.ntc_center)
        else:
            q = Q(pk__isnull=True)
    elif role in ('dept_head', 'dept_deputy'):
        if employee.department:
            q = Q(employee__department=employee.department)
        else:
            q = Q(pk__isnull=True)
    elif role == 'sector_head':
        if employee.department and employee.sector:
            q = Q(
                employee__department=employee.department,
                employee__sector=employee.sector,
            )
        elif employee.department:
            q = Q(employee__department=employee.department)
        else:
            q = Q(pk__isnull=True)
    else:
        q = Q(employee=employee)

    # Делегирования
    delegations = RoleDelegation.objects.filter(
        delegate=employee,
        valid_until__gt=now,
    )
    for d in delegations:
        if d.scope_type == 'center':
            q = q | Q(employee__ntc_center__code=d.scope_value)
        elif d.scope_type == 'dept':
            q = q | Q(employee__department__code=d.scope_value)
        elif d.scope_type == 'sector':
            q = q | Q(employee__sector__code=d.scope_value)
        elif d.scope_type == 'executor':
            q = q | Q(employee__last_name__icontains=d.scope_value)

    return q


# ── Нормализация и валидация plan_hours ─────────────────────────────────────

import re as _re

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
        return {}, None
    if isinstance(ph, str):
        try:
            ph = json.loads(ph)
        except (json.JSONDecodeError, ValueError):
            return {}, 'plan_hours: невалидный JSON'
    if not isinstance(ph, dict):
        return {}, 'plan_hours: ожидается объект'
    if len(ph) > 60:
        return {}, 'plan_hours: слишком много записей (максимум 60)'
    clean = {}
    for k, v in ph.items():
        if not isinstance(k, str) or not _MONTH_KEY_RE.match(k):
            return {}, f'plan_hours: невалидный ключ "{k}" (ожидается YYYY-MM)'
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return {}, f'plan_hours: невалидное значение для ключа "{k}"'
        if fv < 0:
            return {}, f'plan_hours: отрицательное значение для ключа "{k}"'
        if fv > 0:
            clean[k] = fv
    return clean, None


def validate_executors_list(el) -> tuple[list, str | None]:
    """
    Валидирует executors_list.
    Каждый элемент: {'name': str, 'hours': {YYYY-MM: float}}.
    Возвращает (clean_list, error_message).
    """
    if el is None:
        return [], None
    if isinstance(el, str):
        try:
            el = json.loads(el)
        except (json.JSONDecodeError, ValueError):
            return [], 'executors_list: невалидный JSON'
    if not isinstance(el, list):
        return [], 'executors_list: ожидается массив'
    if len(el) > 50:
        return [], 'executors_list: слишком много исполнителей (максимум 50)'
    clean = []
    for i, item in enumerate(el):
        if not isinstance(item, dict):
            return [], f'executors_list[{i}]: ожидается объект'
        name = str(item.get('name', '')).strip()
        if not name:
            return [], f'executors_list[{i}]: имя исполнителя обязательно'
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
        return {}, None
    if isinstance(actions, str):
        try:
            actions = json.loads(actions)
        except (json.JSONDecodeError, ValueError):
            return {}, 'actions: невалидный JSON'
    if not isinstance(actions, dict):
        return {}, 'actions: ожидается объект'
    return actions, None


def norm_plan_hours(ph):
    """
    Нормализация plan_hours. Аналог Flask _norm_plan_hours().
    Принимает dict или str, возвращает dict.
    """
    if ph is None:
        return {}
    if isinstance(ph, str):
        try:
            ph = json.loads(ph)
        except (json.JSONDecodeError, ValueError):
            return {}
    if isinstance(ph, dict):
        return {k: float(v) for k, v in ph.items() if v}
    return {}


def parse_json_hours(raw):
    """Безопасный парсинг JSON plan_hours."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
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
    today = date.today()
    if today.month == 1:
        last_day = date(today.year - 1, 12, 31)
    else:
        last_day = date(
            today.year, today.month - 1,
            calendar.monthrange(today.year, today.month - 1)[1]
        )
    cutoff = f"{today.year}-{str(today.month).zfill(2)}"
    return last_day, cutoff


# ── JSON-сериализация моделей ────────────────────────────────────────────────

class DecimalEncoder(json.JSONEncoder):
    """JSON-энкодер, обрабатывающий Decimal."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def model_to_dict_json(instance, fields=None, exclude=None):
    """Конвертация модели в dict для JSON-ответа."""
    from django.forms.models import model_to_dict
    d = model_to_dict(instance, fields=fields, exclude=exclude)
    # Конвертируем типы
    for k, v in d.items():
        if isinstance(v, Decimal):
            d[k] = float(v)
        elif isinstance(v, date):
            d[k] = v.isoformat()
    return d
