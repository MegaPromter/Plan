"""
API для управления пользователями (admin).

CRUD-операции: User + Employee (OneToOne).
GET     /api/users                -- список пользователей
POST    /api/users                -- создание пользователя
PUT     /api/users/<id>           -- обновление профиля
DELETE  /api/users/<id>           -- удаление пользователя
PUT     /api/users/<id>/password  -- сброс пароля
"""
import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import AdminRequiredJsonMixin, LoginRequiredJsonMixin, parse_json_body
from apps.api.utils import VALID_ROLES
from apps.api.audit import log_action
from apps.employees.models import Employee, Department
from apps.works.models import AuditLog

User = get_user_model()
logger = logging.getLogger(__name__)


def _resolve_position_key(display_name):
    """Преобразует display-имя должности в ключ POSITION_CHOICES."""
    if not display_name:
        return ''
    dl = display_name.lower().strip()
    for key, label in Employee.POSITION_CHOICES:
        if label.lower() == dl:
            return key
    valid_keys = {k for k, _ in Employee.POSITION_CHOICES}
    if display_name in valid_keys:
        return display_name
    return ''


# ── GET / POST /api/users ────────────────────────────────────────────────────

class UserListView(AdminRequiredJsonMixin, View):
    """
    GET  -- список всех пользователей (admin).
    POST -- создание нового пользователя (admin).
    """

    def get(self, request):
        employees = (
            Employee.objects
            .select_related('user', 'department', 'sector', 'ntc_center')
            .order_by('user__username')
        )
        result = []
        for emp in employees:
            result.append({
                'id': emp.user_id,
                'username': emp.user.username,
                'role': emp.role,
                'full_name': emp.full_name,
                'last_name': emp.last_name,
                'first_name': emp.first_name,
                'patronymic': emp.patronymic,
                'dept': emp.department.code if emp.department else '',
                'sector': emp.sector.code if emp.sector else '',
                'center': emp.ntc_center.code if emp.ntc_center else '',
                'position': emp.get_position_display() if emp.position else '',
            })
        return JsonResponse(result, safe=False)

    def post(self, request):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        username = data.get('username', '').strip()
        password = data.get('password', '')
        role = data.get('role', 'user')

        if not username or not password:
            return JsonResponse(
                {'error': 'Логин и пароль обязательны'}, status=400
            )
        if role not in VALID_ROLES:
            return JsonResponse(
                {'error': f'Недопустимая роль: {role}'}, status=400
            )

        try:
            # Атомарная транзакция: User + Employee + подразделения
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                )

                # Создаём профиль Employee
                emp = Employee.objects.create(
                    user=user,
                    role=role,
                    last_name=data.get('last_name', ''),
                    first_name=data.get('first_name', ''),
                    patronymic=data.get('patronymic', ''),
                    position=_resolve_position_key(data.get('position', '')),
                )

                # Устанавливаем подразделение
                from apps.employees.models import Department, Sector, NTCCenter
                dept_code   = data.get('dept', '').strip()
                sector_code = data.get('sector', '').strip()
                center_code = (data.get('ntc_center') or data.get('center') or '').strip()
                if dept_code:
                    dept_obj, _ = Department.objects.get_or_create(code=dept_code, defaults={'name': ''})
                    emp.department = dept_obj
                if sector_code and emp.department:
                    sector_obj, _ = Sector.objects.get_or_create(
                        department=emp.department, code=sector_code, defaults={'name': ''}
                    )
                    emp.sector = sector_obj
                if center_code:
                    center_obj, _ = NTCCenter.objects.get_or_create(code=center_code, defaults={'name': ''})
                    emp.ntc_center = center_obj
                if dept_code or sector_code or center_code:
                    emp.full_clean()
                    emp.save()
        except ValidationError as e:
            return JsonResponse(
                {'error': e.message if hasattr(e, 'message') else str(e)},
                status=400,
            )
        except IntegrityError:
            return JsonResponse(
                {'error': 'Пользователь уже существует'}, status=400
            )

        log_action(request, AuditLog.ACTION_USER_CREATE,
                   object_id=user.pk, object_repr=emp.full_name)
        return JsonResponse({'id': user.pk}, status=201)


# ── PUT / DELETE /api/users/<id> ─────────────────────────────────────────────

class UserDetailView(AdminRequiredJsonMixin, View):
    """
    PUT    -- обновление профиля пользователя.
    DELETE -- удаление пользователя (нельзя удалить себя).
    """

    def put(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        if not data:
            return JsonResponse(
                {'error': 'Нет допустимых полей для обновления'}, status=400
            )

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return JsonResponse(
                {'error': 'Пользователь не найден'}, status=404
            )

        employee = getattr(user, 'employee', None)
        if not employee:
            return JsonResponse(
                {'error': 'Профиль сотрудника не найден'}, status=404
            )

        # Допустимые поля для обновления
        allowed = {
            'role', 'dept', 'sector', 'center', 'ntc_center', 'position',
            'last_name', 'first_name', 'patronymic',
        }
        updates = {k: v for k, v in data.items() if k in allowed}
        # Нормализуем ntc_center -> center
        if 'ntc_center' in updates and 'center' not in updates:
            updates['center'] = updates.pop('ntc_center')
        else:
            updates.pop('ntc_center', None)
        if not updates:
            return JsonResponse(
                {'error': 'Нет допустимых полей для обновления'}, status=400
            )

        # Валидация роли
        if 'role' in updates and updates['role'] not in VALID_ROLES:
            return JsonResponse(
                {'error': f"Недопустимая роль: {updates['role']}"}, status=400
            )

        # Применяем обновления к Employee (в единой транзакции)
        with transaction.atomic():
            return self._apply_employee_updates(request, employee, updates, user)

    def _apply_employee_updates(self, request, employee, updates, user):
        old_role = employee.role
        if 'role' in updates:
            employee.role = updates['role']

        if 'last_name' in updates:
            employee.last_name = updates['last_name']

        if 'first_name' in updates:
            employee.first_name = updates['first_name']

        if 'patronymic' in updates:
            employee.patronymic = updates['patronymic']

        if 'position' in updates:
            employee.position = _resolve_position_key(updates['position'])

        # Обновление подразделений: ищем по коду
        if 'dept' in updates:
            from apps.employees.models import Department
            dept_code = updates['dept'].strip()
            if dept_code:
                dept_obj, _ = Department.objects.get_or_create(
                    code=dept_code, defaults={'name': ''}
                )
                employee.department = dept_obj
            else:
                employee.department = None

        if 'sector' in updates:
            from apps.employees.models import Sector
            sector_code = updates['sector'].strip()
            if sector_code and employee.department:
                sector_obj, _ = Sector.objects.get_or_create(
                    department=employee.department,
                    code=sector_code,
                    defaults={'name': ''},
                )
                employee.sector = sector_obj
            else:
                employee.sector = None

        if 'center' in updates:
            from apps.employees.models import NTCCenter
            center_code = updates['center'].strip()
            if center_code:
                center_obj, _ = NTCCenter.objects.get_or_create(
                    code=center_code, defaults={'name': ''}
                )
                employee.ntc_center = center_obj
            else:
                employee.ntc_center = None

        try:
            employee.full_clean()
        except ValidationError as e:
            return JsonResponse(
                {'error': e.message if hasattr(e, 'message') else str(e)},
                status=400,
            )

        employee.save()

        if 'role' in updates and updates['role'] != old_role:
            log_action(request, AuditLog.ACTION_ROLE_CHANGE,
                       object_id=user.pk, object_repr=employee.full_name,
                       details={'old_role': old_role, 'new_role': updates['role']})
        return JsonResponse({'ok': True})

    def delete(self, request, pk):
        # Нельзя удалить собственную учётную запись
        if pk == request.user.pk:
            return JsonResponse(
                {'error': 'Нельзя удалить собственную учётную запись'},
                status=400,
            )

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return JsonResponse(
                {'error': 'Пользователь не найден'}, status=404
            )

        emp = getattr(user, 'employee', None)
        log_action(request, AuditLog.ACTION_USER_DELETE,
                   object_id=user.pk,
                   object_repr=emp.full_name if emp else user.username)
        user.delete()
        return JsonResponse({'ok': True})


# ── PUT /api/users/<id>/password ─────────────────────────────────────────────

class UserPasswordResetView(AdminRequiredJsonMixin, View):
    """PUT -- сброс пароля пользователя (admin)."""

    def put(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)
        new_pw = data.get('password', '')

        # Валидация пароля через Django password validators
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjValidationError
        try:
            validate_password(new_pw)
        except DjValidationError as e:
            return JsonResponse(
                {'error': '; '.join(e.messages)}, status=400,
            )

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return JsonResponse(
                {'error': 'Пользователь не найден'}, status=404
            )

        user.set_password(new_pw)
        user.save(update_fields=['password'])

        # Устанавливаем флаг обязательной смены пароля
        employee = getattr(user, 'employee', None)
        if employee:
            employee.must_change_password = True
            employee.save(update_fields=['must_change_password'])

        logger.info(
            'Администратор сбросил пароль: admin_id=%s target_uid=%s',
            request.user.pk, pk,
        )
        return JsonResponse({'ok': True})


# ── GET /api/dept_employees/?dept=CODE ───────────────────────────────────────

class DeptEmployeesView(LoginRequiredJsonMixin, View):
    """
    GET -- список сотрудников отдела (для выпадающих списков).
    Доступен всем авторизованным пользователям.
    Параметр: ?dept=CODE (код отдела).
    """

    def get(self, request):
        dept_code = request.GET.get('dept', '').strip()
        if not dept_code:
            return JsonResponse([], safe=False)

        employees = (
            Employee.objects
            .filter(department__code=dept_code, is_active=True)
            .select_related('user')
            .order_by('last_name', 'first_name')
        )
        result = []
        for emp in employees:
            result.append({
                'id': emp.user_id,
                'full_name': emp.full_name,
                'short_name': emp.short_name,
            })
        return JsonResponse(result, safe=False)
