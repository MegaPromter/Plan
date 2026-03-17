"""
Журнал аудита — API для просмотра действий пользователей.
GET /api/audit_log/ — список записей (только admin).
"""
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import AdminRequiredJsonMixin
from apps.works.models import AuditLog


class AuditLogListView(AdminRequiredJsonMixin, View):
    """GET /api/audit_log/ — список записей аудита с пагинацией и фильтрами."""

    def get(self, request):
        qs = AuditLog.objects.select_related('user').order_by('-created_at')

        # Фильтры
        action = request.GET.get('action')
        if action:
            qs = qs.filter(action=action)

        user_id = request.GET.get('user_id')
        if user_id:
            qs = qs.filter(user_id=user_id)

        search = request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(object_repr__icontains=search)

        # Пагинация
        try:
            per_page = min(int(request.GET.get('per_page', 50)), 200)
            page = max(int(request.GET.get('page', 1)), 1)
        except (ValueError, TypeError):
            per_page, page = 50, 1
        total = qs.count()
        offset = (page - 1) * per_page
        entries = qs[offset:offset + per_page]

        items = []
        for e in entries:
            items.append({
                'id': e.id,
                'user': e.user.get_full_name() or e.user.username if e.user else '—',
                'user_id': e.user_id,
                'action': e.action,
                'action_display': e.get_action_display(),
                'object_id': e.object_id,
                'object_repr': e.object_repr,
                'details': e.details,
                'ip_address': e.ip_address,
                'created_at': e.created_at.strftime('%d.%m.%Y %H:%M'),
            })

        return JsonResponse({
            'items': items,
            'total': total,
            'page': page,
            'per_page': per_page,
        })
