"""
Проверка пересечений отсутствий (отпуска + командировки).
POST /api/absence_overlaps/
"""

from datetime import date

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.utils import get_vacation_visibility_filter
from apps.employees.models import BusinessTrip, Vacation


class AbsenceOverlapsView(APIView):
    """Находит пересечения периодов отсутствия между выбранными сотрудниками."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        body = request.data
        if not isinstance(body, dict):
            return Response({"error": "Некорректный JSON"}, status=400)

        employee_ids = body.get("employee_ids", [])
        if not isinstance(employee_ids, list) or len(employee_ids) < 2:
            return Response(
                {"error": "Нужно выбрать минимум 2 сотрудников"}, status=400
            )
        if len(employee_ids) > 100:
            return Response({"error": "Максимум 100 сотрудников"}, status=400)

        # Парсим опциональный диапазон дат
        date_from = _parse_date(body.get("date_from"))
        date_to = _parse_date(body.get("date_to"))
        if date_from and date_to and date_to < date_from:
            return Response({"error": "date_to < date_from"}, status=400)

        include_vacations = body.get("include_vacations", True)
        include_trips = body.get("include_trips", True)
        if not include_vacations and not include_trips:
            return Response(
                {"error": "Нужно включить хотя бы один тип отсутствия"}, status=400
            )

        # Фильтр видимости
        vis = get_vacation_visibility_filter(request.user)

        # Собираем все интервалы отсутствия
        intervals = []

        if include_vacations:
            qs = Vacation.objects.filter(vis, employee_id__in=employee_ids)
            if date_from:
                qs = qs.filter(date_end__gte=date_from)
            if date_to:
                qs = qs.filter(date_start__lte=date_to)
            qs = qs.select_related("employee", "employee__department")
            for v in qs:
                intervals.append(
                    {
                        "employee_id": v.employee_id,
                        "employee_name": v.employee.short_name or str(v.employee),
                        "dept": (
                            v.employee.department.code if v.employee.department else ""
                        ),
                        "start": v.date_start,
                        "end": v.date_end,
                        "type": "vacation",
                        "detail": v.get_vac_type_display(),
                    }
                )

        if include_trips:
            qs = BusinessTrip.objects.filter(vis, employee_id__in=employee_ids)
            qs = qs.exclude(status=BusinessTrip.STATUS_CANCEL)
            if date_from:
                qs = qs.filter(date_end__gte=date_from)
            if date_to:
                qs = qs.filter(date_start__lte=date_to)
            qs = qs.select_related("employee", "employee__department")
            for t in qs:
                intervals.append(
                    {
                        "employee_id": t.employee_id,
                        "employee_name": t.employee.short_name or str(t.employee),
                        "dept": (
                            t.employee.department.code if t.employee.department else ""
                        ),
                        "start": t.date_start,
                        "end": t.date_end,
                        "type": "trip",
                        "detail": t.location,
                    }
                )

        # Поиск пересечений (sweep-line)
        intervals.sort(key=lambda x: x["start"])
        overlaps = []
        n = len(intervals)
        for i in range(n):
            a = intervals[i]
            for j in range(i + 1, n):
                b = intervals[j]
                if b["start"] > a["end"]:
                    break  # дальше не будет пересечений с a
                if a["employee_id"] == b["employee_id"]:
                    continue  # пересечения одного сотрудника не считаем
                ov_start = max(a["start"], b["start"])
                ov_end = min(a["end"], b["end"])
                if ov_start <= ov_end:
                    overlaps.append(
                        {
                            "overlap_start": ov_start.isoformat(),
                            "overlap_end": ov_end.isoformat(),
                            "duration_days": (ov_end - ov_start).days + 1,
                            "employees": [
                                _interval_to_dict(a),
                                _interval_to_dict(b),
                            ],
                        }
                    )

        # Дедупликация: объединяем пересечения с >2 сотрудниками на одном периоде
        overlaps = _merge_overlaps(overlaps)

        # Timeline для визуализации
        emp_map = {}
        for iv in intervals:
            eid = iv["employee_id"]
            if eid not in emp_map:
                emp_map[eid] = {
                    "employee_id": eid,
                    "employee_name": iv["employee_name"],
                    "dept": iv["dept"],
                    "periods": [],
                }
            emp_map[eid]["periods"].append(
                {
                    "start": iv["start"].isoformat(),
                    "end": iv["end"].isoformat(),
                    "type": iv["type"],
                    "detail": iv["detail"],
                }
            )
        timeline = sorted(
            emp_map.values(), key=lambda x: (x["dept"], x["employee_name"])
        )

        # Сводка
        involved = set()
        for ov in overlaps:
            for emp in ov["employees"]:
                involved.add(emp["employee_id"])

        summary = {
            "total_overlaps": len(overlaps),
            "employees_involved": len(involved),
            "max_overlap_days": max(
                (ov["duration_days"] for ov in overlaps), default=0
            ),
        }

        return Response(
            {
                "overlaps": overlaps,
                "timeline": timeline,
                "summary": summary,
            }
        )


def _parse_date(val):
    if not val:
        return None
    try:
        return date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def _interval_to_dict(iv):
    return {
        "employee_id": iv["employee_id"],
        "employee_name": iv["employee_name"],
        "dept": iv["dept"],
        "type": iv["type"],
        "detail": iv["detail"],
        "period_start": iv["start"].isoformat(),
        "period_end": iv["end"].isoformat(),
    }


def _merge_overlaps(overlaps):
    """Объединяет пересечения с одинаковым периодом, собирая всех сотрудников."""
    if not overlaps:
        return []
    merged = {}
    for ov in overlaps:
        key = (ov["overlap_start"], ov["overlap_end"])
        if key not in merged:
            merged[key] = {
                "overlap_start": ov["overlap_start"],
                "overlap_end": ov["overlap_end"],
                "duration_days": ov["duration_days"],
                "employees": [],
            }
        existing_ids = {
            (e["employee_id"], e["period_start"], e["period_end"])
            for e in merged[key]["employees"]
        }
        for emp in ov["employees"]:
            emp_key = (emp["employee_id"], emp["period_start"], emp["period_end"])
            if emp_key not in existing_ids:
                merged[key]["employees"].append(emp)
                existing_ids.add(emp_key)
    result = sorted(merged.values(), key=lambda x: x["overlap_start"])
    return result
