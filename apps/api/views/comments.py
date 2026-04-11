"""
API комментариев к задачам (WorkComment).

  GET    /api/comments/?work_id=N  — список комментариев к задаче
  POST   /api/comments/            — создание комментария
  DELETE /api/comments/<pk>/       — удаление комментария
"""

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.audit import log_action
from apps.api.utils import get_visibility_filter
from apps.works.models import AuditLog, Work, WorkComment

logger = logging.getLogger(__name__)


def _serialize_comment(c):
    """Сериализует WorkComment в dict для JSON-ответа."""
    author_name = ""
    if c.author:
        emp = getattr(c.author, "employee", None)
        if emp:
            author_name = (
                emp.short_name
                or emp.full_name
                or c.author.get_full_name()
                or c.author.username
            )
        else:
            author_name = c.author.get_full_name() or c.author.username
    return {
        "id": c.id,
        "work_id": c.work_id,
        "author": author_name,
        "author_id": c.author_id,
        "text": c.text,
        "created_at": c.created_at.isoformat() if c.created_at else "",
    }


class CommentListView(APIView):
    """GET /api/comments/?work_id=N — список; POST — создание."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            work_id = request.GET.get("work_id")
            if not work_id:
                return Response({"error": "work_id обязателен"}, status=400)

            vis_q = get_visibility_filter(request.user)
            if not Work.objects.filter(vis_q, pk=work_id).exists():
                return Response({"error": "Задача не найдена"}, status=404)

            comments = (
                WorkComment.objects.filter(work_id=work_id)
                .select_related("author", "author__employee")
                .order_by("created_at")[:200]
            )
            return Response([_serialize_comment(c) for c in comments])
        except (ValueError, TypeError) as e:
            logger.warning("CommentListView.get bad request: %s", e)
            return Response({"error": f"Некорректные параметры: {e}"}, status=400)
        except Exception as e:
            logger.error("CommentListView.get error: %s", e, exc_info=True)
            return Response({"error": f"Внутренняя ошибка сервера: {e}"}, status=500)

    def post(self, request):
        """POST /api/comments/ — создание комментария."""
        try:
            return self._create(request)
        except Exception as e:
            logger.error("CommentListView.post error: %s", e, exc_info=True)
            return Response({"error": f"Внутренняя ошибка сервера: {e}"}, status=500)

    def _create(self, request):
        d = request.data
        if not isinstance(d, dict) or not d:
            return Response({"error": "Пустое тело запроса"}, status=400)

        work_id = d.get("work_id")
        text = (d.get("text") or "").strip()

        if not work_id:
            return Response({"error": "work_id обязателен"}, status=400)
        if not text:
            return Response({"error": "Текст комментария обязателен"}, status=400)

        vis_q = get_visibility_filter(request.user)
        if not Work.objects.filter(vis_q, pk=work_id).exists():
            return Response({"error": "Задача не найдена"}, status=404)

        comment = WorkComment.objects.create(
            work_id=work_id,
            author=request.user,
            text=text,
        )
        comment.author = request.user
        return Response(_serialize_comment(comment), status=201)


class CommentDetailView(APIView):
    """DELETE /api/comments/<pk>/ — удаление комментария."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            try:
                comment = WorkComment.objects.select_related("work").get(pk=pk)
            except WorkComment.DoesNotExist:
                return Response({"error": "Комментарий не найден"}, status=404)

            vis_q = get_visibility_filter(request.user)
            if not Work.objects.filter(vis_q, pk=comment.work_id).exists():
                return Response({"error": "Комментарий не найден"}, status=404)

            employee = getattr(request.user, "employee", None)
            is_admin = employee and employee.role in ("admin", "ntc_head", "ntc_deputy")
            if comment.author_id != request.user.id and not is_admin:
                return Response({"error": "Нет прав на удаление"}, status=403)

            log_action(
                request,
                AuditLog.ACTION_COMMENT_DELETE,
                object_id=comment.pk,
                object_repr=f"Комментарий к задаче #{comment.work_id}",
                details={"work_id": comment.work_id, "text": comment.text[:200]},
            )
            comment.delete()
            return Response({"ok": True})
        except Exception as e:
            logger.error("CommentDetailView.delete error: %s", e, exc_info=True)
            return Response({"error": f"Внутренняя ошибка сервера: {e}"}, status=500)
