"""
API уведомлений enterprise-модуля.

GET  /api/enterprise/notifications/               — список уведомлений
POST /api/enterprise/notifications/<id>/read/      — пометить как прочитанное
POST /api/enterprise/notifications/read_all/       — пометить все как прочитанные
GET  /api/enterprise/notifications/unread_count/   — количество непрочитанных
"""
import logging

from django.http import JsonResponse
from django.views import View

from apps.api.mixins import LoginRequiredJsonMixin
from apps.enterprise.models import EnterpriseNotification

logger = logging.getLogger(__name__)


def _serialize_notification(n):
    return {
        'id': n.id,
        'type': n.notification_type,
        'title': n.title,
        'message': n.message,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
        'related_content_type': n.related_content_type_id,
        'related_object_id': n.related_object_id,
    }


class EntNotificationListView(LoginRequiredJsonMixin, View):
    """GET /api/enterprise/notifications/"""

    def get(self, request):
        employee = getattr(request.user, 'employee', None)
        if not employee:
            return JsonResponse({'notifications': []})

        qs = EnterpriseNotification.objects.filter(
            recipient=employee,
        ).order_by('-created_at')[:50]

        return JsonResponse({
            'notifications': [_serialize_notification(n) for n in qs],
        })


class EntNotificationReadView(LoginRequiredJsonMixin, View):
    """POST /api/enterprise/notifications/<id>/read/"""

    def post(self, request, pk):
        employee = getattr(request.user, 'employee', None)
        if not employee:
            return JsonResponse({'error': 'Нет профиля'}, status=403)

        try:
            n = EnterpriseNotification.objects.get(pk=pk, recipient=employee)
        except EnterpriseNotification.DoesNotExist:
            return JsonResponse({'error': 'Уведомление не найдено'}, status=404)

        n.is_read = True
        n.save(update_fields=['is_read'])
        return JsonResponse({'ok': True})


class EntNotificationReadAllView(LoginRequiredJsonMixin, View):
    """POST /api/enterprise/notifications/read_all/"""

    def post(self, request):
        employee = getattr(request.user, 'employee', None)
        if not employee:
            return JsonResponse({'error': 'Нет профиля'}, status=403)

        updated = EnterpriseNotification.objects.filter(
            recipient=employee, is_read=False,
        ).update(is_read=True)

        return JsonResponse({'ok': True, 'updated': updated})


class EntNotificationUnreadCountView(LoginRequiredJsonMixin, View):
    """GET /api/enterprise/notifications/unread_count/"""

    def get(self, request):
        employee = getattr(request.user, 'employee', None)
        if not employee:
            return JsonResponse({'count': 0})

        count = EnterpriseNotification.objects.filter(
            recipient=employee, is_read=False,
        ).count()

        return JsonResponse({'count': count})
