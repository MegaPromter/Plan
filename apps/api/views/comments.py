"""
API комментариев к задачам (WorkComment).

  GET    /api/comments/?work_id=N  — список комментариев к задаче
  POST   /api/comments/            — создание комментария
  DELETE /api/comments/<pk>/       — удаление комментария
"""

import logging

from django.http import JsonResponse
from django.views import View

from apps.api.audit import log_action
from apps.api.mixins import LoginRequiredJsonMixin, parse_json_body
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


# ---------------------------------------------------------------------------
#  GET /api/comments/?work_id=N
# ---------------------------------------------------------------------------


class CommentListView(LoginRequiredJsonMixin, View):
    """GET /api/comments/?work_id=N — список комментариев к задаче."""

    def get(self, request):
        try:
            work_id = request.GET.get("work_id")
            if not work_id:
                return JsonResponse({"error": "work_id обязателен"}, status=400)

            vis_q = get_visibility_filter(request.user)
            if not Work.objects.filter(vis_q, pk=work_id).exists():
                return JsonResponse({"error": "Задача не найдена"}, status=404)

            comments = (
                WorkComment.objects.filter(work_id=work_id)
                .select_related("author", "author__employee")
                .order_by("created_at")[:200]
            )
            result = [_serialize_comment(c) for c in comments]
            return JsonResponse(result, safe=False)
        except (ValueError, TypeError) as e:
            logger.warning("CommentListView.get bad request: %s", e)
            return JsonResponse({"error": f"Некорректные параметры: {e}"}, status=400)
        except Exception as e:
            logger.error("CommentListView.get error: %s", e, exc_info=True)
            return JsonResponse(
                {"error": f"Внутренняя ошибка сервера: {e}"}, status=500
            )

    def post(self, request):
        """POST /api/comments/ — создание комментария."""
        try:
            return self._create(request)
        except Exception as e:
            logger.error("CommentListView.post error: %s", e, exc_info=True)
            return JsonResponse(
                {"error": f"Внутренняя ошибка сервера: {e}"}, status=500
            )

    def _create(self, request):
        d = parse_json_body(request)
        if d is None:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)
        if not d:
            return JsonResponse({"error": "Пустое тело запроса"}, status=400)

        work_id = d.get("work_id")
        text = (d.get("text") or "").strip()

        if not work_id:
            return JsonResponse({"error": "work_id обязателен"}, status=400)
        if not text:
            return JsonResponse({"error": "Текст комментария обязателен"}, status=400)

        vis_q = get_visibility_filter(request.user)
        if not Work.objects.filter(vis_q, pk=work_id).exists():
            return JsonResponse({"error": "Задача не найдена"}, status=404)

        comment = WorkComment.objects.create(
            work_id=work_id,
            author=request.user,
            text=text,
        )
        # Подгружаем связанные объекты для сериализации
        comment.author = request.user
        return JsonResponse(_serialize_comment(comment), status=201)


# ---------------------------------------------------------------------------
#  DELETE /api/comments/<pk>/
# ---------------------------------------------------------------------------


class CommentDetailView(LoginRequiredJsonMixin, View):
    """DELETE /api/comments/<pk>/ — удаление комментария."""

    def delete(self, request, pk):
        try:
            try:
                comment = WorkComment.objects.select_related("work").get(pk=pk)
            except WorkComment.DoesNotExist:
                return JsonResponse({"error": "Комментарий не найден"}, status=404)

            # Проверяем доступ к задаче
            vis_q = get_visibility_filter(request.user)
            if not Work.objects.filter(vis_q, pk=comment.work_id).exists():
                return JsonResponse({"error": "Комментарий не найден"}, status=404)

            # Удалять может только автор или admin
            employee = getattr(request.user, "employee", None)
            is_admin = employee and employee.role in ("admin", "ntc_head", "ntc_deputy")
            if comment.author_id != request.user.id and not is_admin:
                return JsonResponse({"error": "Нет прав на удаление"}, status=403)

            log_action(
                request,
                AuditLog.ACTION_COMMENT_DELETE,
                object_id=comment.pk,
                object_repr=f"Комментарий к задаче #{comment.work_id}",
                details={"work_id": comment.work_id, "text": comment.text[:200]},
            )
            comment.delete()
            return JsonResponse({"ok": True})
        except Exception as e:
            logger.error("CommentDetailView.delete error: %s", e, exc_info=True)
            return JsonResponse(
                {"error": f"Внутренняя ошибка сервера: {e}"}, status=500
            )
