"""
API для делегирования прав (role delegations).

CRUD-операции над RoleDelegation.
GET     /api/delegations          -- список делегирований
POST    /api/delegations          -- создание делегирования
DELETE  /api/delegations/<id>     -- отзыв делегирования
"""
import logging
from datetime import datetime

from django.http import JsonResponse
from django.utils import timezone
from django.views import View

from apps.api.mixins import LoginRequiredJsonMixin, parse_json_body
from apps.employees.models import Employee, RoleDelegation

logger = logging.getLogger(__name__)

# Допустимые типы области делегирования
_VALID_SCOPE_TYPES = {'center', 'dept', 'sector', 'executor'}


# ── GET / POST /api/delegations ──────────────────────────────────────────────

class DelegationListView(LoginRequiredJsonMixin, View):
    """
    GET  -- список делегирований текущего пользователя
            (выданных + полученных, или все для admin).
    POST -- создание нового делегирования (только writer-роли).
    """

    def get(self, request):
        employee = getattr(request.user, 'employee', None)
        if not employee:
            return JsonResponse([], safe=False)

        role_filter = request.GET.get('role', 'both')

        if role_filter == 'delegator':
            qs = (
                RoleDelegation.objects
                .filter(delegator=employee)
                .select_related('delegate__user')
                .order_by('-created_at')
            )
            result = []
            for rd in qs:
                result.append({
                    'id': rd.pk,
                    'delegator_id': rd.delegator_id,
                    'delegate_id': rd.delegate_id,
                    'scope_type': rd.scope_type,
                    'scope_value': rd.scope_value,
                    'delegator_write': rd.can_write,
                    'valid_until': rd.valid_until.isoformat() if rd.valid_until else None,
                    'created_at': rd.created_at.isoformat() if rd.created_at else None,
                    'delegate_username': rd.delegate.user.username,
                    'delegate_full_name': rd.delegate.full_name,
                })

        elif role_filter == 'delegate':
            qs = (
                RoleDelegation.objects
                .filter(delegate=employee)
                .select_related('delegator__user')
                .order_by('-created_at')
            )
            result = []
            for rd in qs:
                result.append({
                    'id': rd.pk,
                    'delegator_id': rd.delegator_id,
                    'delegate_id': rd.delegate_id,
                    'scope_type': rd.scope_type,
                    'scope_value': rd.scope_value,
                    'delegator_write': rd.can_write,
                    'valid_until': rd.valid_until.isoformat() if rd.valid_until else None,
                    'created_at': rd.created_at.isoformat() if rd.created_at else None,
                    'delegator_username': rd.delegator.user.username,
                    'delegator_full_name': rd.delegator.full_name,
                })

        else:
            # both -- все делегирования, связанные с текущим пользователем
            qs = (
                RoleDelegation.objects
                .filter(
                    models_Q_delegator_or_delegate(employee)
                )
                .order_by('-created_at')
            )
            result = []
            for rd in qs:
                result.append({
                    'id': rd.pk,
                    'delegator_id': rd.delegator_id,
                    'delegate_id': rd.delegate_id,
                    'scope_type': rd.scope_type,
                    'scope_value': rd.scope_value,
                    'delegator_write': rd.can_write,
                    'valid_until': rd.valid_until.isoformat() if rd.valid_until else None,
                    'created_at': rd.created_at.isoformat() if rd.created_at else None,
                })

        return JsonResponse(result, safe=False)

    def post(self, request):
        employee = getattr(request.user, 'employee', None)
        if not employee:
            return JsonResponse(
                {'error': 'Профиль сотрудника не найден'}, status=400
            )

        role = employee.role
        if role == 'user':
            return JsonResponse(
                {'error': 'Исполнители не могут делегировать права'}, status=403
            )

        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        delegate_id = data.get('delegate_id')
        scope_type = data.get('scope_type', '')
        scope_value = (data.get('scope_value') or '').strip()
        can_write = bool(data.get('delegator_write', False))
        valid_until_str = data.get('valid_until', '')

        # Валидация
        if not delegate_id:
            return JsonResponse(
                {'error': 'Не указан получатель делегирования'}, status=400
            )

        try:
            delegate_id = int(delegate_id)
        except (TypeError, ValueError):
            return JsonResponse(
                {'error': 'Некорректный ID получателя'}, status=400
            )
        if delegate_id == employee.pk:
            return JsonResponse(
                {'error': 'Нельзя делегировать самому себе'}, status=400
            )

        if scope_type not in _VALID_SCOPE_TYPES:
            return JsonResponse(
                {'error': 'Недопустимый тип области (center/dept/sector/executor)'},
                status=400,
            )

        if not scope_value:
            return JsonResponse(
                {'error': 'Не указано значение области'}, status=400
            )

        # Парсинг даты
        try:
            valid_until = datetime.fromisoformat(valid_until_str)
            if timezone.is_naive(valid_until):
                valid_until = timezone.make_aware(valid_until)
            if valid_until <= timezone.now():
                return JsonResponse(
                    {'error': 'Срок действия должен быть в будущем'}, status=400
                )
        except (ValueError, TypeError):
            return JsonResponse(
                {'error': 'Неверный формат даты (ожидается ISO 8601)'},
                status=400,
            )

        # Проверка зоны видимости менеджера
        user_center = employee.ntc_center.code if employee.ntc_center else ''
        user_dept = employee.department.code if employee.department else ''
        user_sector = employee.sector.code if employee.sector else ''

        if role in ('ntc_head', 'ntc_deputy'):
            if scope_type == 'center' and scope_value != user_center:
                return JsonResponse(
                    {'error': 'Можно делегировать только свой НТЦ'}, status=403
                )
        elif role in ('dept_head', 'dept_deputy'):
            if scope_type == 'center':
                return JsonResponse(
                    {'error': 'Начальник отдела не может делегировать права НТЦ'},
                    status=403,
                )
            if scope_type == 'dept' and scope_value != user_dept:
                return JsonResponse(
                    {'error': 'Можно делегировать только свой отдел'}, status=403
                )
        elif role == 'sector_head':
            if scope_type in ('center', 'dept'):
                return JsonResponse(
                    {'error': 'Начальник сектора не может делегировать права выше сектора'},
                    status=403,
                )
            if scope_type == 'sector' and scope_value != user_sector:
                return JsonResponse(
                    {'error': 'Можно делегировать только свой сектор'}, status=403
                )

        # Проверяем, что получатель существует
        try:
            delegate = Employee.objects.get(pk=int(delegate_id))
        except Employee.DoesNotExist:
            return JsonResponse(
                {'error': 'Пользователь-получатель не найден'}, status=400
            )

        rd = RoleDelegation.objects.create(
            delegator=employee,
            delegate=delegate,
            scope_type=scope_type,
            scope_value=scope_value,
            can_write=can_write,
            valid_until=valid_until,
        )

        logger.info(
            'Delegation %s: delegator=%s -> delegate=%s scope=%s:%s write=%s until=%s',
            rd.pk, employee.pk, delegate.pk, scope_type, scope_value,
            can_write, valid_until_str,
        )
        return JsonResponse({'id': rd.pk, 'ok': True}, status=201)


# ── DELETE /api/delegations/<id> ─────────────────────────────────────────────

class DelegationDetailView(LoginRequiredJsonMixin, View):
    """DELETE -- отзыв делегирования. Только delegator или admin."""

    def delete(self, request, pk):
        employee = getattr(request.user, 'employee', None)
        if not employee:
            return JsonResponse(
                {'error': 'Профиль сотрудника не найден'}, status=400
            )

        try:
            rd = RoleDelegation.objects.get(pk=pk)
        except RoleDelegation.DoesNotExist:
            return JsonResponse(
                {'error': 'Делегирование не найдено'}, status=404
            )

        # Только delegator или admin могут отозвать
        if employee.role != 'admin' and rd.delegator_id != employee.pk:
            return JsonResponse(
                {'error': 'Нет прав для отзыва этого делегирования'},
                status=403,
            )

        rd.delete()
        logger.info(
            'Delegation %s revoked by user %s', pk, employee.pk
        )
        return JsonResponse({'ok': True})


# ── Вспомогательные функции ──────────────────────────────────────────────────

def models_Q_delegator_or_delegate(employee):
    """Q-объект: delegator=employee OR delegate=employee."""
    from django.db.models import Q
    return Q(delegator=employee) | Q(delegate=employee)
