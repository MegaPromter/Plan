"""
API «Снимок месяца» — единый источник правды для СП и Аналитики-Отчётов.

GET /api/analytics/month_snapshot/
    ?month=YYYY-MM       (обязательный; например 2026-03)
    &dept=021            (необязательный; код отдела)
    &sector_id=7         (необязательный; id сектора)
    &center_id=1         (необязательный; id НТЦ-центра)
    &project_id=12       (необязательный; id УП-проекта)

Возвращает сводку по двум группам:
  1) Задачи месяца: done / done_early / overdue / inwork
  2) Долги прошлых месяцев: debt_closed / debt_hanging

Правила (исторический снимок на конец выбранного месяца):
  • Долг (is_debt) — дедлайн строго ДО начала месяца М, и отчёта до начала М нет.
    Такие задачи — всегда в группе «Долги», даже если есть plan_hours на М.
  • Задача месяца — has_plan_in(M) = True И is_debt = False.
  • done                  — дедлайн ∈ M, отчёт сдан в M.
  • done_early            — дедлайн > M_end, отчёт сдан в M.
  • overdue               — дедлайн ∈ M и УЖЕ наступил (дедлайн ≤ today), отчёта в M нет.
    Для прошедших месяцев today не применяется — весь месяц считается прошедшим.
  • inwork                — дедлайн > today (ещё не наступил) ИЛИ дедлайн > M_end, отчёта в M нет.
  • debt_closed           — долг, отчёт сдан в M.
  • debt_hanging          — долг, отчёта в M нет.
"""

from datetime import date

from django.db.models import Exists, OuterRef, Q, Subquery
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.utils import get_visibility_filter
from apps.works.models import Work, WorkReport


def _parse_month(month_str):
    """'2026-03' -> (2026, 3) или None при ошибке."""
    if not month_str:
        return None
    try:
        y_str, m_str = month_str.split("-")
        y, m = int(y_str), int(m_str)
        if 1 <= m <= 12 and 2000 <= y <= 2100:
            return (y, m)
    except (ValueError, AttributeError):
        pass
    return None


def _month_bounds(year, month):
    """Возвращает (M_start, M_end_next) — первое число месяца и первое число следующего."""
    m_start = date(year, month, 1)
    if month == 12:
        m_end = date(year + 1, 1, 1)
    else:
        m_end = date(year, month + 1, 1)
    return m_start, m_end


def _has_plan_in_month(plan_hours, year, month):
    """Есть ли в plan_hours ненулевые часы на YYYY-MM?"""
    if not plan_hours:
        return False
    key = f"{year:04d}-{month:02d}"
    val = plan_hours.get(key)
    if val is None:
        return False
    try:
        return float(val) > 0
    except (TypeError, ValueError):
        return False


def _as_date(value):
    """Приводит datetime/date к date. None остаётся None."""
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date()
    return value


def _classify(work, year, month, m_start, m_end, today):
    """
    Возвращает код статуса для задачи в снимке месяца (year, month).

    Возможные коды:
      - "debt_closed"   — долг, закрыт в месяце М
      - "debt_hanging"  — долг, висит
      - "done"          — задача месяца, выполнена в срок
      - "done_early"    — задача месяца, выполнена с опережением
      - "overdue"       — задача месяца, просрочена
      - "inwork"        — задача месяца, в работе
      - None            — задача не попадает в снимок месяца
    """
    deadline = work.date_end
    first_report = _as_date(getattr(work, "_first_report_date", None))

    # 1) Проверка на долг — приоритет абсолютный
    #    Дедлайн был ДО начала М и до начала М отчёта не было.
    is_debt = False
    if deadline and deadline < m_start:
        if first_report is None or first_report >= m_start:
            is_debt = True

    reported_in_month = first_report is not None and m_start <= first_report < m_end

    if is_debt:
        return "debt_closed" if reported_in_month else "debt_hanging"

    # 2) Не долг — проверяем, попадает ли в «задачи месяца»
    has_plan = _has_plan_in_month(work.plan_hours, year, month)
    if not has_plan:
        return None

    if deadline and m_start <= deadline < m_end:
        # Дедлайн в этом месяце
        if reported_in_month:
            return "done"
        # Для текущего (ещё не завершённого) месяца — «просрочено» только если
        # дедлайн уже наступил. Если срок впереди — задача «в работе».
        if today < m_end and deadline > today:
            return "inwork"
        return "overdue"

    if deadline and deadline >= m_end:
        # Дедлайн позже месяца
        return "done_early" if reported_in_month else "inwork"

    # Дедлайн отсутствует — трактуем как «в работе»
    if deadline is None:
        return "done_early" if reported_in_month else "inwork"

    return None


class MonthSnapshotView(APIView):
    """GET /api/analytics/month_snapshot/ — снимок месяца по задачам."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        month_str = request.GET.get("month", "").strip()
        parsed = _parse_month(month_str)
        if not parsed:
            return Response(
                {"error": "Параметр month обязателен в формате YYYY-MM"},
                status=400,
            )
        year, month = parsed
        m_start, m_end = _month_bounds(year, month)
        # Сегодняшняя дата нужна, чтобы в ТЕКУЩЕМ месяце не записывать в
        # «просрочено» задачи с ещё не наступившим дедлайном.
        today = timezone.now().date()

        dept_code = (request.GET.get("dept") or "").strip()
        sector_id = request.GET.get("sector_id")
        center_id = request.GET.get("center_id")
        project_id = request.GET.get("project_id")

        # ── Базовый queryset ─────────────────────────────────────────
        vis_q = get_visibility_filter(request.user)

        has_reports = Exists(WorkReport.objects.filter(work=OuterRef("pk")))
        first_report = Subquery(
            WorkReport.objects.filter(work=OuterRef("pk"))
            .order_by("created_at")
            .values("created_at")[:1]
        )

        # plan_hours_key — ключ для поиска «на этот месяц»
        plan_key = f"{year:04d}-{month:02d}"

        qs = (
            Work.objects.filter(vis_q, show_in_plan=True)
            .annotate(
                _has_reports=has_reports,
                _first_report_date=first_report,
            )
            .select_related("department", "sector", "executor", "project", "pp_project")
        )

        # Фильтры по подразделению / проекту
        if dept_code:
            qs = qs.filter(department__code=dept_code)
        if sector_id:
            try:
                qs = qs.filter(sector_id=int(sector_id))
            except ValueError:
                pass
        if center_id:
            try:
                qs = qs.filter(department__ntc_center_id=int(center_id))
            except ValueError:
                pass
        if project_id:
            try:
                pid = int(project_id)
                qs = qs.filter(Q(project_id=pid) | Q(pp_project__up_project_id=pid))
            except ValueError:
                pass

        # Сужаем выборку ДО Python-классификации:
        # В снимок потенциально входят:
        #   а) задачи с plan_hours на этот месяц (кандидаты на «задачу месяца»);
        #   б) задачи с дедлайном до M_start (кандидаты на долг).
        # Работы, у которых ни того ни другого — отсекаем, чтобы не тянуть лишнее.
        qs = qs.filter(Q(plan_hours__has_key=plan_key) | Q(date_end__lt=m_start))

        # ── Классификация в Python ──────────────────────────────────
        buckets = {
            "done": 0,
            "done_early": 0,
            "overdue": 0,
            "inwork": 0,
            "debt_closed": 0,
            "debt_hanging": 0,
        }
        task_ids_by_bucket = {k: [] for k in buckets}

        for w in qs:
            code = _classify(w, year, month, m_start, m_end, today)
            if code is None:
                continue
            buckets[code] += 1
            task_ids_by_bucket[code].append(w.id)

        month_total = (
            buckets["done"]
            + buckets["done_early"]
            + buckets["overdue"]
            + buckets["inwork"]
        )
        debts_total = buckets["debt_closed"] + buckets["debt_hanging"]
        month_closed = buckets["done"] + buckets["done_early"]

        def _pct(num, denom):
            return round(num / denom * 100, 1) if denom > 0 else 0.0

        return Response(
            {
                "month": f"{year:04d}-{month:02d}",
                "filters": {
                    "dept": dept_code or None,
                    "sector_id": int(sector_id) if sector_id else None,
                    "center_id": int(center_id) if center_id else None,
                    "project_id": int(project_id) if project_id else None,
                },
                "month_tasks": {
                    "total": month_total,
                    "closed": month_closed,
                    "closed_pct": _pct(month_closed, month_total),
                    "done": buckets["done"],
                    "done_pct": _pct(buckets["done"], month_total),
                    "done_early": buckets["done_early"],
                    "done_early_pct": _pct(buckets["done_early"], month_total),
                    "overdue": buckets["overdue"],
                    "overdue_pct": _pct(buckets["overdue"], month_total),
                    "inwork": buckets["inwork"],
                    "inwork_pct": _pct(buckets["inwork"], month_total),
                    "task_ids": {
                        "done": task_ids_by_bucket["done"],
                        "done_early": task_ids_by_bucket["done_early"],
                        "overdue": task_ids_by_bucket["overdue"],
                        "inwork": task_ids_by_bucket["inwork"],
                    },
                },
                "debts": {
                    "total": debts_total,
                    "closed": buckets["debt_closed"],
                    "closed_pct": _pct(buckets["debt_closed"], debts_total),
                    "hanging": buckets["debt_hanging"],
                    "hanging_pct": _pct(buckets["debt_hanging"], debts_total),
                    "task_ids": {
                        "closed": task_ids_by_bucket["debt_closed"],
                        "hanging": task_ids_by_bucket["debt_hanging"],
                    },
                },
            }
        )
