"""
Журнал аудита — API для просмотра действий пользователей.
GET /api/audit_log/ — список записей (только admin).
"""

from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.drf_utils import IsAdminPermission
from apps.works.models import AuditLog

# Разрешённые поля для сортировки
_SORT_FIELDS = {
    "created_at": "created_at",
    "date": "created_at",
    "user": "user__last_name",
    "action": "action",
    "object_repr": "object_repr",
    "ip_address": "ip_address",
}


class AuditLogListView(APIView):
    """GET /api/audit_log/ — список записей аудита с пагинацией и фильтрами."""

    permission_classes = [IsAdminPermission]

    def get(self, request):
        qs = AuditLog.objects.select_related("user")

        # ── Фильтры ────────────────────────────────────────────────
        action = request.GET.get("action")
        if action:
            qs = qs.filter(action=action)

        user_filter = request.GET.get("user", "").strip()
        if user_filter:
            qs = qs.filter(
                Q(user__last_name__icontains=user_filter)
                | Q(user__first_name__icontains=user_filter)
                | Q(user__username__icontains=user_filter)
            )

        search = request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(object_repr__icontains=search)

        ip_filter = request.GET.get("ip", "").strip()
        if ip_filter:
            qs = qs.filter(ip_address__icontains=ip_filter)

        date_from = request.GET.get("date_from", "").strip()
        if date_from:
            d = parse_date(date_from)
            if d:
                qs = qs.filter(created_at__date__gte=d)

        date_to = request.GET.get("date_to", "").strip()
        if date_to:
            d = parse_date(date_to)
            if d:
                qs = qs.filter(created_at__date__lte=d)

        # ── Сортировка ─────────────────────────────────────────────
        sort_key = request.GET.get("sort", "created_at")
        sort_dir = request.GET.get("dir", "desc")
        db_field = _SORT_FIELDS.get(sort_key, "created_at")
        if sort_dir == "asc":
            qs = qs.order_by(db_field)
        else:
            qs = qs.order_by("-" + db_field)

        # ── Пагинация ──────────────────────────────────────────────
        try:
            per_page = min(int(request.GET.get("per_page", 50)), 200)
            page = max(int(request.GET.get("page", 1)), 1)
        except (ValueError, TypeError):
            per_page, page = 50, 1
        total = qs.count()
        offset = (page - 1) * per_page
        entries = qs[offset : offset + per_page]

        items = [
            {
                "id": e.id,
                "user": (e.user.get_full_name() or e.user.username if e.user else "—"),
                "user_id": e.user_id,
                "action": e.action,
                "action_display": e.get_action_display(),
                "object_id": e.object_id,
                "object_repr": e.object_repr,
                "details": e.details,
                "ip_address": e.ip_address,
                "date": e.created_at.strftime("%d.%m.%Y"),
                "created_at": e.created_at.strftime("%d.%m.%Y %H:%M"),
            }
            for e in entries
        ]

        return Response(
            {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
            }
        )
