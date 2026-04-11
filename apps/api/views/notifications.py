"""
API-вьюхи для центра уведомлений.

GET  /api/notifications/             — список последних 50 уведомлений
POST /api/notifications/sync/        — генерация уведомлений о сроках
POST /api/notifications/<pk>/read/   — пометить одно как прочитанное
POST /api/notifications/read_all/    — пометить все как прочитанные
GET  /api/notifications/unread_count/ — количество непрочитанных (для badge)
"""

from datetime import timedelta

from django.core.cache import cache
from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.works.models import Notification, Work, WorkReport


def _notif_cache_key(user):
    return f"notif_unread:{user.pk}"


def _sync_deadline_notifications(user):
    """Создаёт/обновляет уведомления о приближающихся сроках и просрочках личных задач."""
    emp = getattr(user, "employee", None)
    if not emp:
        return

    today = timezone.now().date()
    week_ahead = today + timedelta(days=7)

    # Личные задачи: executor = я, show_in_plan = True, есть date_end, нет отчётов
    tasks = (
        Work.objects.filter(
            ~Exists(WorkReport.objects.filter(work=OuterRef("pk"))),
            executor=emp,
            show_in_plan=True,
            date_end__isnull=False,
        )
        .filter(date_end__lte=week_ahead)
        .values("id", "work_name", "date_end", "row_code")
        .distinct()
    )

    # Существующие непрочитанные уведомления по задачам
    existing = set(
        Notification.objects.filter(
            user=user,
            is_read=False,
            link__startswith="/works/plan/?task=",
        ).values_list("link", flat=True)
    )

    for t in tasks:
        link = f"/works/plan/?task={t['id']}"
        if link in existing:
            continue

        d = t["date_end"]
        task_name = t["work_name"] or t["row_code"] or f"Задача #{t['id']}"

        if d < today:
            days_overdue = (today - d).days
            Notification.objects.create(
                user=user,
                type="overdue",
                title=f"Просрочена: {task_name}",
                message=f'Просрочена на {days_overdue} дн. (срок: {d.strftime("%d.%m.%Y")})',
                link=link,
            )
        elif d <= week_ahead:
            days_left = (d - today).days
            if days_left == 0:
                msg = "Срок сдачи — сегодня!"
            elif days_left == 1:
                msg = "Срок сдачи — завтра"
            else:
                msg = f'Осталось {days_left} дн. (срок: {d.strftime("%d.%m.%Y")})'
            Notification.objects.create(
                user=user,
                type="warning",
                title=f"Приближается срок: {task_name}",
                message=msg,
                link=link,
            )


class NotificationSyncView(APIView):
    """POST /api/notifications/sync/ — генерация уведомлений о сроках."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _sync_deadline_notifications(request.user)
        return Response({"ok": True})


class NotificationListView(APIView):
    """GET /api/notifications/ — последние 50 уведомлений текущего пользователя."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)[:50]
        items = [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "link": n.link,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in qs
        ]
        return Response({"items": items})


class NotificationReadView(APIView):
    """POST /api/notifications/<pk>/read/ — пометить уведомление как прочитанное."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        updated = Notification.objects.filter(
            pk=pk, user=request.user, is_read=False
        ).update(is_read=True)
        if not updated:
            return Response(
                {"error": "Уведомление не найдено или уже прочитано"}, status=404
            )
        cache.delete(_notif_cache_key(request.user))
        return Response({"ok": True})


class NotificationReadAllView(APIView):
    """POST /api/notifications/read_all/ — пометить все уведомления как прочитанные."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True
        )
        cache.delete(_notif_cache_key(request.user))
        return Response({"ok": True, "updated": count})


class NotificationUnreadCountView(APIView):
    """GET /api/notifications/unread_count/ — количество непрочитанных."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        key = _notif_cache_key(request.user)
        count = cache.get(key)
        if count is None:
            count = Notification.objects.filter(
                user=request.user, is_read=False
            ).count()
            cache.set(key, count, 10)
        return Response({"count": count})
