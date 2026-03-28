"""
API-вьюхи для центра уведомлений.

GET  /api/notifications/             — список последних 50 уведомлений
POST /api/notifications/sync/        — генерация уведомлений о сроках (без побочных эффектов в GET)
POST /api/notifications/<pk>/read/   — пометить одно как прочитанное
POST /api/notifications/read_all/    — пометить все как прочитанные
GET  /api/notifications/unread_count/ — количество непрочитанных (для badge)
"""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Exists, OuterRef
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from apps.works.models import Notification, Work, WorkReport


def _notif_cache_key(user):
    return f'notif_unread:{user.pk}'


def _sync_deadline_notifications(user):
    """Создаёт/обновляет уведомления о приближающихся сроках и просрочках личных задач."""
    emp = getattr(user, 'employee', None)
    if not emp:
        return

    today = timezone.now().date()
    week_ahead = today + timedelta(days=7)

    # Личные задачи: executor = я, show_in_plan = True, есть date_end, нет отчётов
    tasks = Work.objects.filter(
        ~Exists(WorkReport.objects.filter(work=OuterRef('pk'))),  # нет ни одного отчёта → задача не выполнена
        executor=emp,
        show_in_plan=True,
        date_end__isnull=False,
    ).filter(
        date_end__lte=week_ahead,  # срок ≤ неделя вперёд (включая просрочки)
    ).values('id', 'work_name', 'date_end', 'row_code').distinct()

    # Существующие непрочитанные уведомления по задачам (чтобы не дублировать)
    existing = set(
        Notification.objects.filter(
            user=user,
            is_read=False,
            link__startswith='/works/plan/?task=',
        ).values_list('link', flat=True)
    )

    for t in tasks:
        link = f"/works/plan/?task={t['id']}"
        if link in existing:
            continue  # уже есть непрочитанное

        d = t['date_end']
        task_name = t['work_name'] or t['row_code'] or f"Задача #{t['id']}"

        if d < today:
            days_overdue = (today - d).days
            Notification.objects.create(
                user=user,
                type='overdue',
                title=f'Просрочена: {task_name}',
                message=f'Просрочена на {days_overdue} дн. (срок: {d.strftime("%d.%m.%Y")})',
                link=link,
            )
        elif d <= week_ahead:
            days_left = (d - today).days
            if days_left == 0:
                msg = 'Срок сдачи — сегодня!'
            elif days_left == 1:
                msg = 'Срок сдачи — завтра'
            else:
                msg = f'Осталось {days_left} дн. (срок: {d.strftime("%d.%m.%Y")})'
            Notification.objects.create(
                user=user,
                type='warning',
                title=f'Приближается срок: {task_name}',
                message=msg,
                link=link,
            )


@method_decorator(login_required, name='dispatch')
class NotificationSyncView(View):
    """POST /api/notifications/sync/ — генерация уведомлений о сроках."""

    def post(self, request):
        _sync_deadline_notifications(request.user)
        return JsonResponse({'ok': True})


@method_decorator(login_required, name='dispatch')
class NotificationListView(View):
    """GET /api/notifications/ — последние 50 уведомлений текущего пользователя."""

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)[:50]
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
            return JsonResponse({'error': 'Уведомление не найдено или уже прочитано'}, status=404)
        cache.delete(_notif_cache_key(request.user))
        return JsonResponse({'ok': True})


@method_decorator(login_required, name='dispatch')
class NotificationReadAllView(View):
    """POST /api/notifications/read_all/ — пометить все уведомления как прочитанные."""

    def post(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        cache.delete(_notif_cache_key(request.user))
        return JsonResponse({'ok': True, 'updated': count})


@method_decorator(login_required, name='dispatch')
class NotificationUnreadCountView(View):
    """GET /api/notifications/unread_count/ — количество непрочитанных."""

    def get(self, request):
        key = _notif_cache_key(request.user)
        count = cache.get(key)
        if count is None:
            count = Notification.objects.filter(user=request.user, is_read=False).count()
            cache.set(key, count, 10)
        return JsonResponse({'count': count})
