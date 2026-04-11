"""
API проектов производственного плана (PPProject).

  GET    /api/pp_projects        — список проектов ПП
  POST   /api/pp_projects        — создание проекта ПП
  PUT    /api/pp_projects/<id>   — обновление проекта ПП
  DELETE /api/pp_projects/<id>   — удаление проекта ПП
"""

import logging

from django.db import transaction
from django.db.models import Count
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.drf_utils import IsAdminPermission
from apps.works.models import PPProject, Work

logger = logging.getLogger(__name__)


def _serialize_project(proj, row_count=None):
    """Сериализует PPProject в dict для JSON-ответа."""
    d = {
        "id": proj.id,
        "name": proj.name or "",
        "directory_id": proj.directory_id,
        "up_project_id": proj.up_project_id,
        "up_project_name": (
            (proj.up_project.name_full or proj.up_project.name_short)
            if proj.up_project
            else ""
        ),
        "up_product_id": proj.up_product_id,
        "up_product_name": proj.up_product.name if proj.up_product else "",
        "created_at": proj.created_at.isoformat() if proj.created_at else "",
    }
    if row_count is not None:
        d["row_count"] = row_count
    return d


class PPProjectListView(APIView):
    """GET — список проектов ПП."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            projects = (
                PPProject.objects.select_related("up_project", "up_product")
                .annotate(row_count=Count("pp_works"))
                .order_by("-id")
            )
            result = [_serialize_project(p, row_count=p.row_count) for p in projects]
            resp = Response(result)
            resp["X-Total-Count"] = len(result)
            return resp
        except Exception as e:
            logger.error("PPProjectListView.get error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)


class PPProjectCreateView(APIView):
    """POST /api/pp_projects — создание проекта ПП (только admin)."""

    permission_classes = [IsAdminPermission]

    def post(self, request):
        try:
            return self._create(request)
        except Exception as e:
            logger.error("PPProjectCreateView error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def _create(self, request):
        d = request.data
        name = (d.get("name") or "").strip()
        if not name:
            return Response({"error": "Название обязательно"}, status=400)

        directory_id = d.get("directory_id") or None
        up_project_id = d.get("up_project_id") or None
        up_product_id = d.get("up_product_id") or None
        project = PPProject.objects.create(
            name=name,
            directory_id=directory_id,
            up_project_id=up_project_id,
            up_product_id=up_product_id,
        )
        return Response(
            {
                "id": project.id,
                "name": project.name,
                "up_project_id": project.up_project_id,
                "up_product_id": project.up_product_id,
            }
        )


class PPProjectDetailView(APIView):
    """PUT /api/pp_projects/<id>; DELETE /api/pp_projects/<id> — только admin."""

    permission_classes = [IsAdminPermission]

    def put(self, request, pk):
        try:
            return self._update(request, pk)
        except Exception as e:
            logger.error("PPProjectDetailView.put error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def delete(self, request, pk):
        try:
            return self._delete(request, pk)
        except Exception as e:
            logger.error("PPProjectDetailView.delete error: %s", e, exc_info=True)
            return Response({"error": "Внутренняя ошибка сервера"}, status=500)

    def _update(self, request, pk):
        d = request.data
        name = (d.get("name") or "").strip()
        if not name:
            return Response({"error": "Название обязательно"}, status=400)

        try:
            project = PPProject.objects.get(pk=pk)
        except PPProject.DoesNotExist:
            return Response({"error": "Проект не найден"}, status=404)

        project.name = name
        up_project_id = d.get("up_project_id", project.up_project_id)
        project.up_project_id = up_project_id or None
        up_product_id = d.get("up_product_id", project.up_product_id)
        project.up_product_id = up_product_id or None
        project.save(update_fields=["name", "up_project_id", "up_product_id"])
        return Response({"ok": True})

    def _delete(self, request, pk):
        try:
            project = PPProject.objects.get(pk=pk)
        except PPProject.DoesNotExist:
            return Response({"error": "Проект не найден"}, status=404)

        with transaction.atomic():
            Work.objects.filter(pp_project=project, show_in_pp=True).delete()
            project.delete()

        return Response({"ok": True})
