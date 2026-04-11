"""
API этапов проекта (PPStage).

GET    /api/projects/<pk>/stages/              — список этапов проекта
POST   /api/projects/<pk>/stages/create/       — создание этапа
PUT    /api/projects/<pk>/stages/<stage_id>/   — обновление этапа
DELETE /api/projects/<pk>/stages/<stage_id>/   — удаление этапа
"""

import logging

from django.db.models import Exists, OuterRef, Prefetch
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.drf_utils import IsWriterPermission
from apps.works.models import PPStage, Project, TaskExecutor, Work, WorkReport

logger = logging.getLogger(__name__)


def _serialize_stage(s):
    return {
        "id": s.id,
        "name": s.name,
        "stage_number": s.stage_number,
        "work_order": s.work_order,
        "row_code": s.row_code,
        "order": s.order,
    }


def _sum_plan_hours(ph):
    """Сумма всех значений из JSONField plan_hours."""
    if not ph:
        return 0.0
    total = 0.0
    for v in ph.values():
        try:
            total += float(v)
        except (ValueError, TypeError):
            pass
    return total


def _calc_labor_for_stages(stages):
    """Считает запланированную и потраченную трудоёмкость по этапам."""
    stage_ids = [s.id for s in stages]
    if not stage_ids:
        return {}

    has_reports = Exists(WorkReport.objects.filter(work=OuterRef("pk")))
    works = (
        Work.objects.filter(pp_stage_id__in=stage_ids, show_in_pp=True)
        .annotate(_has_reports=has_reports)
        .prefetch_related(
            Prefetch(
                "task_executors",
                queryset=TaskExecutor.objects.all(),
                to_attr="_prefetched_executors",
            )
        )
        .only("id", "pp_stage_id", "labor", "plan_hours", "work_name")
    )

    result = {sid: {"planned": 0.0, "spent": 0.0, "works": []} for sid in stage_ids}

    for w in works:
        sid = w.pp_stage_id
        labor_val = float(w.labor) if w.labor is not None else 0.0
        if w.labor is not None:
            result[sid]["planned"] += labor_val

        has_rep = getattr(w, "_has_reports", False)
        if has_rep:
            result[sid]["spent"] += _sum_plan_hours(w.plan_hours)
            for te in getattr(w, "_prefetched_executors", []):
                result[sid]["spent"] += _sum_plan_hours(te.plan_hours)

        result[sid]["works"].append(
            {
                "id": w.id,
                "name": w.work_name or "(без названия)",
                "labor": round(labor_val, 2),
                "has_report": has_rep,
            }
        )

    for sid in result:
        result[sid]["planned"] = round(result[sid]["planned"], 2)
        result[sid]["spent"] = round(result[sid]["spent"], 2)

    return result


class PPStageListView(APIView):
    """GET — список этапов проекта УП."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            try:
                proj = Project.objects.get(pk=pk)
            except Project.DoesNotExist:
                return Response({"error": "Проект не найден"}, status=404)
            stages = list(proj.stages.order_by("order", "id"))
            labor_map = _calc_labor_for_stages(stages)
            result = []
            for s in stages:
                d = _serialize_stage(s)
                labor = labor_map.get(s.id, {})
                d["planned_labor"] = labor.get("planned", 0)
                d["spent_labor"] = labor.get("spent", 0)
                d["works"] = labor.get("works", [])
                result.append(d)
            return Response(result)
        except Exception as e:
            logger.error("PPStageListView.get: %s", e, exc_info=True)
            return Response({"error": "Ошибка сервера"}, status=500)


class PPStageCreateView(APIView):
    """POST — создание этапа."""

    permission_classes = [IsWriterPermission]

    def post(self, request, pk):
        try:
            try:
                proj = Project.objects.get(pk=pk)
            except Project.DoesNotExist:
                return Response({"error": "Проект не найден"}, status=404)
            d = request.data
            name = (d.get("name") or "").strip()
            if not name:
                return Response({"error": "Наименование обязательно"}, status=400)
            stage = PPStage.objects.create(
                project=proj,
                name=name,
                stage_number=(d.get("stage_number") or "").strip(),
                work_order=(d.get("work_order") or "").strip(),
                row_code=(d.get("row_code") or "").strip(),
                order=d.get("order", 0) or 0,
            )
            return Response(_serialize_stage(stage), status=201)
        except Exception as e:
            logger.error("PPStageCreateView.post: %s", e, exc_info=True)
            return Response({"error": "Ошибка сервера"}, status=500)


class PPStageDetailView(APIView):
    """PUT — обновление; DELETE — удаление этапа."""

    permission_classes = [IsWriterPermission]

    def put(self, request, pk, stage_id):
        try:
            try:
                stage = PPStage.objects.get(pk=stage_id, project_id=pk)
            except PPStage.DoesNotExist:
                return Response({"error": "Этап не найден"}, status=404)
            d = request.data
            name = (d.get("name") or "").strip()
            if not name:
                return Response({"error": "Наименование обязательно"}, status=400)
            stage.name = name
            stage.stage_number = (d.get("stage_number") or "").strip()
            stage.work_order = (d.get("work_order") or "").strip()
            stage.row_code = (d.get("row_code") or "").strip()
            if "order" in d:
                stage.order = d["order"] or 0
            stage.save()
            return Response(_serialize_stage(stage))
        except Exception as e:
            logger.error("PPStageDetailView.put: %s", e, exc_info=True)
            return Response({"error": "Ошибка сервера"}, status=500)

    def delete(self, request, pk, stage_id):
        try:
            try:
                stage = PPStage.objects.get(pk=stage_id, project_id=pk)
            except PPStage.DoesNotExist:
                return Response({"error": "Этап не найден"}, status=404)
            stage.works.update(pp_stage=None)
            stage.delete()
            return Response({"ok": True})
        except Exception as e:
            logger.error("PPStageDetailView.delete: %s", e, exc_info=True)
            return Response({"error": "Ошибка сервера"}, status=500)
