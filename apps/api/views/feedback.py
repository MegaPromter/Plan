"""
API: Замечания и предложения.

GET    /api/feedback/       — список (admin: все, остальные: свои)
POST   /api/feedback/       — создание (multipart/form-data)
PUT    /api/feedback/<id>/  — обновление статуса (admin)
DELETE /api/feedback/<id>/  — удаление (admin)
"""

from django.http import JsonResponse
from django.views import View

from apps.api.mixins import LoginRequiredJsonMixin
from apps.works.models import Feedback, FeedbackAttachment

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 МБ
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _serialize(fb, current_user=None):
    return {
        "id": fb.pk,
        "user_id": fb.user_id,
        "user_name": (getattr(fb.user, "employee", None) and fb.user.employee.full_name)
        or fb.user.get_full_name()
        or fb.user.username,
        "is_own": current_user and fb.user_id == current_user.pk,
        "category": fb.category,
        "category_display": fb.get_category_display(),
        "text": fb.text,
        "status": fb.status,
        "status_display": fb.get_status_display(),
        "admin_comment": fb.admin_comment,
        "screenshot": fb.screenshot.url if fb.screenshot else "",
        "screenshots": [
            {"id": att.pk, "url": att.image.url} for att in fb.attachments.all()
        ],
        "created_at": fb.created_at.isoformat(),
    }


class FeedbackListView(LoginRequiredJsonMixin, View):
    """GET — список, POST — создание."""

    def get(self, request):
        qs = Feedback.objects.select_related("user", "user__employee").prefetch_related(
            "attachments"
        )

        # Обычные пользователи видят только свои замечания, admin — все
        emp = getattr(request.user, "employee", None)
        is_admin = (emp and emp.role == "admin") if emp else request.user.is_superuser
        if not is_admin:
            qs = qs.filter(user=request.user)

        status_filter = request.GET.get("status", "")
        if status_filter:
            qs = qs.filter(status=status_filter)
        category_filter = request.GET.get("category", "")
        if category_filter:
            qs = qs.filter(category=category_filter)

        items = [_serialize(fb, request.user) for fb in qs[:500]]
        return JsonResponse(items, safe=False)

    def post(self, request):
        category = request.POST.get("category", "other")
        text = request.POST.get("text", "").strip()
        if not text:
            return JsonResponse({"error": "Текст обязателен"}, status=400)

        valid_cats = {c[0] for c in Feedback.CATEGORY_CHOICES}
        if category not in valid_cats:
            category = "other"

        # Валидация загружаемых файлов
        all_files = []
        if "screenshot" in request.FILES:
            all_files.append(request.FILES["screenshot"])
        all_files.extend(request.FILES.getlist("screenshots"))
        for f in all_files:
            if f.size > MAX_UPLOAD_SIZE:
                return JsonResponse(
                    {"error": f"Файл «{f.name}» слишком большой (макс. 5 МБ)"},
                    status=400,
                )
            if f.content_type not in ALLOWED_IMAGE_TYPES:
                return JsonResponse(
                    {
                        "error": f"Файл «{f.name}»: допустимы только изображения (JPEG, PNG, GIF, WebP)"
                    },
                    status=400,
                )

        fb = Feedback(user=request.user, category=category, text=text)
        if "screenshot" in request.FILES:
            fb.screenshot = request.FILES["screenshot"]
        fb.save()
        # Дополнительные скриншоты
        for f in request.FILES.getlist("screenshots"):
            FeedbackAttachment.objects.create(feedback=fb, image=f)
        return JsonResponse({"id": fb.pk, "feedback": _serialize(fb)}, status=201)


class FeedbackDetailView(LoginRequiredJsonMixin, View):
    """PUT — обновление, DELETE — удаление, POST — обновление с файлом."""

    def post(self, request, pk):
        """POST с _method=PUT — для multipart/form-data (файл скриншота)."""
        if request.POST.get("_method") != "PUT":
            return JsonResponse({"error": "Method not allowed"}, status=405)
        return self._update(request, pk, multipart=True)

    def put(self, request, pk):
        return self._update(request, pk, multipart=False)

    def _update(self, request, pk, multipart=False):
        emp = getattr(request.user, "employee", None)
        is_admin = (emp and emp.role == "admin") if emp else request.user.is_superuser

        try:
            fb = Feedback.objects.get(pk=pk)
        except Feedback.DoesNotExist:
            return JsonResponse({"error": "Не найдено"}, status=404)

        is_own = fb.user_id == request.user.pk
        if not is_admin and not is_own:
            return JsonResponse({"error": "Доступ запрещён"}, status=403)

        if multipart:
            data = request.POST.dict()
        else:
            import json

            try:
                data = json.loads(request.body)
            except (json.JSONDecodeError, ValueError):
                return JsonResponse({"error": "Invalid JSON"}, status=400)

        changed = []

        # Автор может редактировать текст, категорию и скриншот
        if is_own:
            if "text" in data and data["text"].strip():
                fb.text = data["text"].strip()
                changed.append("text")
            if "category" in data:
                valid_cats = {c[0] for c in Feedback.CATEGORY_CHOICES}
                if data["category"] in valid_cats:
                    fb.category = data["category"]
                    changed.append("category")
            if multipart and "screenshot" in request.FILES:
                fb.screenshot = request.FILES["screenshot"]
                changed.append("screenshot")
            if multipart:
                for f in request.FILES.getlist("screenshots"):
                    FeedbackAttachment.objects.create(feedback=fb, image=f)

        # Только admin может менять статус и комментарий
        if is_admin:
            if "status" in data:
                valid_statuses = {s[0] for s in Feedback.STATUS_CHOICES}
                if data["status"] in valid_statuses:
                    fb.status = data["status"]
                    changed.append("status")
            if "admin_comment" in data:
                fb.admin_comment = data["admin_comment"]
                changed.append("admin_comment")

        if changed:
            fb.save(update_fields=changed + ["updated_at"])

        return JsonResponse({"ok": True, "feedback": _serialize(fb, request.user)})

    def delete(self, request, pk):
        emp = getattr(request.user, "employee", None)
        is_admin = (emp and emp.role == "admin") if emp else request.user.is_superuser
        if not is_admin:
            return JsonResponse({"error": "Доступ запрещён"}, status=403)

        try:
            fb = Feedback.objects.get(pk=pk)
        except Feedback.DoesNotExist:
            return JsonResponse({"error": "Не найдено"}, status=404)

        fb.delete()
        return JsonResponse({"ok": True})


class FeedbackAttachmentDeleteView(LoginRequiredJsonMixin, View):
    """DELETE /api/feedback/attachment/<pk>/ — удаление вложения (автор или admin)."""

    def delete(self, request, pk):
        try:
            att = FeedbackAttachment.objects.select_related("feedback").get(pk=pk)
        except FeedbackAttachment.DoesNotExist:
            return JsonResponse({"error": "Не найдено"}, status=404)

        emp = getattr(request.user, "employee", None)
        is_admin = (emp and emp.role == "admin") if emp else request.user.is_superuser
        is_own = att.feedback.user_id == request.user.pk

        if not is_admin and not is_own:
            return JsonResponse({"error": "Доступ запрещён"}, status=403)

        att.delete()
        return JsonResponse({"ok": True})
