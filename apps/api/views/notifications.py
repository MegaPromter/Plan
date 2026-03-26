"""
API-вьюхи для центра уведомлений.

GET  /api/notifications/          — список последних 20 уведомлений
POST /api/notifications/<pk>/read/ — пометить одно как прочитанное
POST /api/notifications/read_all/  — пометить все как прочитанные
GET  /api/notifications/unread_count/ — количество непрочитанных (для badge)
"""
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

from apps.works.models import Notification


@method_decorator(login_required, name='dispatch')
class NotificationListView(View):
    """GET /api/notifications/ — последние 20 уведомлений текущего пользователя."""

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)[:20]
        items = []
        for n in qs:
            items.append({
                'id': n.id,
                'type': n.type,
                'title': n.title,
                'message': n.message,
                'link': n.link,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
            })
        return JsonResponse({'items': items})


@method_decorator(login_required, name='dispatch')
class NotificationReadView(View):
    """POST /api/notifications/<pk>/read/ — пометить уведомление как прочитанное."""

    def post(self, request, pk):
        updated = Notification.objects.filter(pk=pk, user=request.user, is_read=False).update(is_read=True)
        if not updated:
            return JsonResponse({'detail': 'not found or already read'}, status=404)
        return JsonResponse({'ok': True})


@method_decorator(login_required, name='dispatch')
class NotificationReadAllView(View):
    """POST /api/notifications/read_all/ — пометить все уведомления как прочитанные."""

    def post(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'ok': True, 'updated': count})


@method_decorator(login_required, name='dispatch')
class NotificationUnreadCountView(View):
    """GET /api/notifications/unread_count/ — количество непрочитанных."""

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return JsonResponse({'count': count})
