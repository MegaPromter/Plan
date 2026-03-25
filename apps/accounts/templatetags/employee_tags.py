"""
Шаблонные теги для безопасного обращения к профилю Employee.
"""
from django import template  # базовый модуль Django для создания библиотек шаблонных тегов

# Регистр библиотеки тегов — обязательный объект, который Django ищет в templatetags-модулях.
# Все фильтры и теги регистрируются через декораторы этого объекта.
register = template.Library()


@register.filter  # декоратор: регистрирует функцию как шаблонный фильтр ({{ value|has_employee }})
def has_employee(user):
    """{{ request.user|has_employee }} — True если у пользователя есть профиль Employee."""
    try:
        # Обращаемся к reverse OneToOne-связи user.employee.
        # Если профиль существует — bool() возвращает True.
        return bool(user.employee)
    except (AttributeError, TypeError):
        # Если профиля нет (RelatedObjectDoesNotExist) или пользователь анонимный — возвращаем False
        return False


@register.filter  # регистрируем как фильтр: {{ request.user|is_writer }}
def is_writer(user):
    """{{ request.user|is_writer }} — True если пользователь имеет право записи."""
    if user.is_superuser:
        # Суперпользователь Django всегда имеет право записи без проверки роли Employee
        return True
    try:
        # Делегируем проверку свойству is_writer модели Employee
        # is_writer возвращает True для всех ролей, кроме 'user'
        return user.employee.is_writer
    except (AttributeError, TypeError):
        # Профиль Employee отсутствует или пользователь не аутентифицирован
        return False


@register.filter  # регистрируем как фильтр: {{ request.user|is_admin_role }}
def is_admin_role(user):
    """{{ request.user|is_admin_role }} — True если роль admin."""
    if user.is_superuser:
        # Суперпользователь Django приравнивается к роли admin
        return True
    try:
        # Импортируем модель Employee здесь, чтобы избежать circular import на уровне модуля
        from apps.employees.models import Employee
        # Сравниваем строковое значение роли с константой ROLE_ADMIN ('admin')
        return user.employee.role == Employee.ROLE_ADMIN
    except (AttributeError, TypeError):
        # Профиль Employee отсутствует или пользователь анонимный
        return False


@register.simple_tag(takes_context=True)  # тег с контекстом: {% employee_initial %}
def employee_initial(context):
    """{% employee_initial %} — Первая буква имени для аватара."""
    request = context.get('request')
    if not request:
        return '?'
    try:
        name = request.user.employee.short_name or request.user.username
    except (AttributeError, TypeError):
        name = request.user.username
    return name[0].upper() if name else '?'


@register.simple_tag(takes_context=True)  # тег, получающий контекст шаблона: {% employee_name %}
def employee_name(context):
    """{% employee_name %} — Возвращает короткое имя или username."""
    # Получаем объект запроса из контекста шаблона (добавляется context_processor'ом request)
    request = context.get('request')
    if not request:
        # Контекст без request (например, в email-шаблонах) — возвращаем пустую строку
        return ''
    try:
        # short_name — свойство Employee, обычно «Фамилия И.О.»
        # Если short_name пустой/None — используем username как запасной вариант
        return request.user.employee.short_name or request.user.username
    except (AttributeError, TypeError):
        # Профиль Employee отсутствует — возвращаем username как безопасный fallback
        return request.user.username


@register.simple_tag(takes_context=True)  # тег с контекстом: {% employee_role %}
def employee_role(context):
    """{% employee_role %} — Возвращает отображаемую роль."""
    # Получаем объект запроса из контекста шаблона
    request = context.get('request')
    if not request:
        # Нет контекста запроса — нечего отображать
        return ''
    try:
        # get_role_display() возвращает человекочитаемое название роли из choices
        # (например, 'admin' → 'Администратор', 'user' → 'Пользователь')
        return request.user.employee.get_role_display()
    except (AttributeError, TypeError):
        # Профиль Employee отсутствует: для суперпользователя показываем специальную метку,
        # для обычного пользователя без профиля — пустую строку
        return 'Суперпользователь' if request.user.is_superuser else ''
