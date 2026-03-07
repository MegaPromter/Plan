"""
Шаблонные теги для безопасного обращения к профилю Employee.
"""
from django import template

register = template.Library()


@register.filter
def has_employee(user):
    """{{ request.user|has_employee }} — True если у пользователя есть профиль Employee."""
    try:
        return bool(user.employee)
    except Exception:
        return False


@register.filter
def is_writer(user):
    """{{ request.user|is_writer }} — True если пользователь имеет право записи."""
    if user.is_superuser:
        return True
    try:
        return user.employee.is_writer
    except Exception:
        return False


@register.filter
def is_admin_role(user):
    """{{ request.user|is_admin_role }} — True если роль admin."""
    if user.is_superuser:
        return True
    try:
        from apps.employees.models import Employee
        return user.employee.role == Employee.ROLE_ADMIN
    except Exception:
        return False


@register.simple_tag(takes_context=True)
def employee_name(context):
    """{% employee_name %} — Возвращает короткое имя или username."""
    request = context.get('request')
    if not request:
        return ''
    try:
        return request.user.employee.short_name or request.user.username
    except Exception:
        return request.user.username


@register.simple_tag(takes_context=True)
def employee_role(context):
    """{% employee_role %} — Возвращает отображаемую роль."""
    request = context.get('request')
    if not request:
        return ''
    try:
        return request.user.employee.get_role_display()
    except Exception:
        return 'Суперпользователь' if request.user.is_superuser else ''
