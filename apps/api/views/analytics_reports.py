"""
API отчётов о выполнении плана — иерархическая загрузка по ролям.

GET /api/analytics/reports/
    ?years=2026         (через запятую; по умолчанию текущий год)
    &months=3,4         (через запятую; пусто = все)
    &project_ids=5,12   (фильтр по УП-проектам)
    &product_ids=3,7    (фильтр по изделиям)
    &dept_codes=021,022 (фильтр по отделам)
    &center_ids=1       (фильтр по центрам)
    &sector_ids=7,8     (фильтр по секторам)
    &executor_ids=12,15 (фильтр по сотрудникам)

Возвращает метрики выполнения: задач/выполнено/просрочено/долги/план(ч)/%.
Иерархия drill-down: Центры → Отделы → Секторы → Сотрудники → Задачи.
"""

from collections import defaultdict
from datetime import date

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.utils import get_visibility_filter
from apps.employees.models import Department, Employee, NTCCenter, Sector
from apps.works.models import Project, ProjectProduct, TaskExecutor, Work, WorkReport

from .analytics_plan import _get_role_info, _int_list_param, _str_list_param


def _period_start(years, months_filter):
    """Начало отчётного периода: первый день минимального выбранного месяца/года."""
    y = min(years)
    m = min(months_filter) if months_filter else 1
    return date(y, m, 1)


def _classify_task(w, today, period_start):
    """
    Классифицирует задачу:
      done     — есть отчёт (work_report)
      debt     — отчёта нет, срок < начало периода (долг из прошлых периодов)
      overdue  — отчёта нет, срок прошёл внутри/после начала периода, но < сегодня
      inwork   — срок ещё не наступил или дата не задана
    """
    is_done = getattr(w, "_done", False)
    if is_done:
        return "done"
    effective_end = w.date_end or w.deadline
    if not effective_end:
        return "inwork"
    if effective_end < period_start:
        return "debt"
    if effective_end < today:
        return "overdue"
    return "inwork"


def _debt_depth(effective_end, period_start):
    """Глубина долга: 1m / 2_3m / 3plus."""
    delta = (period_start - effective_end).days
    if delta <= 30:
        return "1m"
    elif delta <= 90:
        return "2_3m"
    return "3plus"


def _debt_depth_label(depth):
    labels = {"1m": "1 мес", "2_3m": "2–3 мес", "3plus": "3+ мес"}
    return labels.get(depth, depth)


def _task_plan_hours_in_period(w, years_set, months_set):
    """Сумма plan_hours задачи, попадающих в выбранный период."""
    total = 0.0
    ph = w.plan_hours or {}
    for k, v in ph.items():
        try:
            y_str, m_str = k.split("-")
            y_int, m_int = int(y_str), int(m_str)
            if y_int in years_set and (not months_set or m_int in months_set):
                total += float(v) if v else 0
        except (ValueError, TypeError):
            pass
    return round(total, 2)


def _has_hours_in_period(w, years_set, months_set):
    """Есть ли у задачи план. часы в выбранном периоде."""
    ph = w.plan_hours or {}
    for k, v in ph.items():
        try:
            y_str, m_str = k.split("-")
            y_int, m_int = int(y_str), int(m_str)
            if y_int in years_set and (not months_set or m_int in months_set):
                if v and float(v) > 0:
                    return True
        except (ValueError, TypeError):
            pass
    return False


def _project_name(w):
    """Название проекта задачи."""
    if w.project:
        return w.project.name
    if w.pp_project and w.pp_project.up_project:
        return w.pp_project.up_project.name
    if w.pp_project:
        return w.pp_project.name
    return ""


def _project_id(w):
    """ID проекта задачи (для группировки)."""
    if w.project_id:
        return w.project_id
    if w.pp_project and w.pp_project.up_project_id:
        return w.pp_project.up_project_id
    return 0


def _build_report_metrics(works, years, months_filter, today):
    """
    Считает метрики выполнения для набора задач.
    Возвращает dict со счётчиками и списками задач-долгов.
    """
    years_set = set(years)
    months_set = set(months_filter) if months_filter else None
    ps = _period_start(years, months_filter)

    total = 0
    done = 0
    overdue = 0
    inwork = 0
    debts_1m = 0
    debts_2_3m = 0
    debts_3plus = 0
    plan_hours = 0.0
    debt_tasks = []

    for w in works:
        # Проверяем, относится ли задача к периоду
        has_hours = _has_hours_in_period(w, years_set, months_set)
        effective_end = w.date_end or w.deadline

        status = _classify_task(w, today, ps)

        # Долги всегда включаем (они из прошлых периодов)
        if status == "debt":
            total += 1
            depth = _debt_depth(effective_end, ps)
            if depth == "1m":
                debts_1m += 1
            elif depth == "2_3m":
                debts_2_3m += 1
            else:
                debts_3plus += 1
            days_overdue = (today - effective_end).days if effective_end else 0
            debt_tasks.append(
                {
                    "id": w.id,
                    "work_name": w.work_name or w.work_num or "",
                    "project_name": _project_name(w),
                    "executor": w.executor.short_name if w.executor else "",
                    "dept": w.department.code if w.department else "",
                    "date_end": effective_end.isoformat() if effective_end else "",
                    "days_overdue": days_overdue,
                    "depth": depth,
                }
            )
            plan_hours += _task_plan_hours_in_period(w, years_set, months_set)
            continue

        # Остальные — только если имеют часы в периоде
        if not has_hours:
            continue

        total += 1
        ph = _task_plan_hours_in_period(w, years_set, months_set)
        plan_hours += ph

        if status == "done":
            done += 1
        elif status == "overdue":
            overdue += 1
        else:
            inwork += 1

    debts_total = debts_1m + debts_2_3m + debts_3plus
    completion_pct = round(done / total * 100, 1) if total > 0 else 0

    # Сортируем долги по убыванию просрочки
    debt_tasks.sort(key=lambda t: -t["days_overdue"])

    return {
        "total": total,
        "done": done,
        "overdue": overdue,
        "inwork": inwork,
        "debts_1m": debts_1m,
        "debts_2_3m": debts_2_3m,
        "debts_3plus": debts_3plus,
        "debts_total": debts_total,
        "debt_tasks": debt_tasks[:50],  # Топ-50 долгов
        "debt_tasks_total": len(debt_tasks),
        "plan_hours": round(plan_hours, 1),
        "completion_pct": completion_pct,
    }


def _build_project_breakdown(works, years, months_filter, today):
    """Группировка метрик по проектам."""
    project_works = defaultdict(list)
    project_names = {}
    for w in works:
        pid = _project_id(w)
        project_works[pid].append(w)
        if pid and pid not in project_names:
            project_names[pid] = _project_name(w)

    projects = []
    for pid in sorted(project_works.keys()):
        if pid == 0:
            continue
        metrics = _build_report_metrics(project_works[pid], years, months_filter, today)
        if metrics["total"] == 0:
            continue
        projects.append(
            {
                "id": pid,
                "name": project_names.get(pid, f"Проект {pid}"),
                **metrics,
            }
        )
    # Сортируем по убыванию общего кол-ва задач
    projects.sort(key=lambda p: -p["total"])
    return projects


def _build_employee_report(emp_id, works, years, months_filter, today):
    """Отчёт по одному сотруднику: метрики + список задач."""
    years_set = set(years)
    months_set = set(months_filter) if months_filter else None
    ps = _period_start(years, months_filter)

    tasks = []
    total = 0
    done_count = 0
    overdue_count = 0
    inwork_count = 0
    debts_count = 0
    plan_hours_sum = 0.0

    for w in works:
        # Определяем plan_hours этого сотрудника для задачи
        ph_raw = {}
        if w.executor_id == emp_id:
            ph_raw = w.plan_hours or {}
        else:
            for te in getattr(w, "_prefetched_executors", []):
                if te.executor_id == emp_id:
                    ph_raw = te.plan_hours or {}
                    break

        if not ph_raw and w.executor_id != emp_id:
            continue

        # Фильтруем часы по периоду
        ph_filtered = 0.0
        has_hours = False
        for k, v in ph_raw.items():
            try:
                y_str, m_str = k.split("-")
                y_int, m_int = int(y_str), int(m_str)
                if y_int in years_set and (not months_set or m_int in months_set):
                    val = float(v) if v else 0
                    ph_filtered += val
                    if val > 0:
                        has_hours = True
            except (ValueError, TypeError):
                pass
        ph_filtered = round(ph_filtered, 2)

        status = _classify_task(w, today, ps)

        # Долги включаем всегда, остальные — только с часами
        if status != "debt" and not has_hours:
            continue

        effective_end = w.date_end or w.deadline
        days_overdue = 0
        if status in ("overdue", "debt") and effective_end:
            days_overdue = (today - effective_end).days

        total += 1
        plan_hours_sum += ph_filtered
        if status == "done":
            done_count += 1
        elif status == "overdue":
            overdue_count += 1
        elif status == "debt":
            debts_count += 1
        else:
            inwork_count += 1

        tasks.append(
            {
                "id": w.id,
                "work_name": w.work_name or w.work_num or "",
                "project_name": _project_name(w),
                "date_start": w.date_start.isoformat() if w.date_start else "",
                "date_end": effective_end.isoformat() if effective_end else "",
                "plan_hours": ph_filtered,
                "status": status,
                "days_overdue": days_overdue,
            }
        )

    # Сортировка: долги (по убыванию просрочки), просроченные, выполненные, в работе
    status_order = {"debt": 0, "overdue": 1, "done": 2, "inwork": 3}
    tasks.sort(key=lambda t: (status_order.get(t["status"], 9), -t["days_overdue"]))

    completion_pct = round(done_count / total * 100, 1) if total > 0 else 0
    return {
        "total": total,
        "done": done_count,
        "overdue": overdue_count,
        "inwork": inwork_count,
        "debts_total": debts_count,
        "plan_hours": round(plan_hours_sum, 1),
        "completion_pct": completion_pct,
        "tasks": tasks,
    }


class ReportsAnalyticsView(APIView):
    """GET /api/analytics/reports/ — отчёты о выполнении плана."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        emp = getattr(request.user, "employee", None)

        # ── Параметры ──
        years = _int_list_param(request, "years") or [today.year]
        months_filter = _int_list_param(request, "months")
        project_ids = _int_list_param(request, "project_ids")
        product_ids = _int_list_param(request, "product_ids")
        dept_codes = _str_list_param(request, "dept_codes")
        center_ids = _int_list_param(request, "center_ids")
        sector_ids = _int_list_param(request, "sector_ids")
        executor_ids = _int_list_param(request, "executor_ids")

        # ── Базовый queryset ──
        vis_q = get_visibility_filter(request.user)
        has_reports = Exists(WorkReport.objects.filter(work=OuterRef("pk")))

        base = (
            Work.objects.filter(vis_q, show_in_plan=True)
            .annotate(_done=has_reports)
            .select_related(
                "department",
                "department__ntc_center",
                "sector",
                "executor",
                "project",
                "pp_project",
                "pp_project__up_project",
            )
        )

        if center_ids:
            base = base.filter(department__ntc_center_id__in=center_ids)

        # Фильтр по годам + долги из прошлых периодов
        year_q = Q(date_start__isnull=True, date_end__isnull=True)
        min_year = min(years) - 1  # Захватываем прошлый год для долгов
        for y in list(years) + [min_year]:
            year_q |= (
                Q(date_start__year__lte=y, date_end__year__gte=y)
                | Q(date_start__year=y)
                | Q(date_end__year=y)
                | Q(date_start__isnull=True, date_end__year__gte=min_year)
                | Q(date_end__isnull=True, date_start__year__lte=max(years))
            )
        base = base.filter(year_q)

        if product_ids:
            base = base.filter(pp_project__up_product_id__in=product_ids)
        elif project_ids:
            base = base.filter(
                Q(project_id__in=project_ids)
                | Q(pp_project__up_project_id__in=project_ids)
            )

        te_qs = TaskExecutor.objects.select_related("executor")
        base = base.prefetch_related(
            Prefetch("task_executors", queryset=te_qs, to_attr="_prefetched_executors")
        )

        works_list = list(base)

        # ── Маршрутизация по ролям (аналогично PlanAnalyticsView) ──
        role_info = _get_role_info(emp)
        role = role_info["role"]

        if executor_ids:
            if len(executor_ids) == 1:
                return self._respond_employee(
                    request,
                    executor_ids[0],
                    works_list,
                    years,
                    months_filter,
                    role_info,
                    emp,
                    today,
                )
            # Несколько сотрудников — показать их сектор/отдел
            filtered = [
                w
                for w in works_list
                if w.executor_id in set(executor_ids)
                or any(
                    te.executor_id in set(executor_ids)
                    for te in getattr(w, "_prefetched_executors", [])
                )
            ]
            return self._respond_all_depts(
                request,
                filtered,
                years,
                months_filter,
                role_info,
                emp,
                today,
            )

        if role == "user":
            if emp and emp.sector_id:
                return self._respond_sector(
                    request,
                    emp.sector_id,
                    works_list,
                    years,
                    months_filter,
                    role_info,
                    emp,
                    today,
                )
            return self._respond_employee(
                request,
                emp.pk if emp else 0,
                works_list,
                years,
                months_filter,
                role_info,
                emp,
                today,
            )

        if role == "sector_head" and not dept_codes and not sector_ids:
            dc = emp.department.code if emp and emp.department else ""
            if dc:
                return self._respond_dept(
                    request,
                    dc,
                    works_list,
                    years,
                    months_filter,
                    role_info,
                    emp,
                    today,
                )

        if role in ("dept_head", "dept_deputy") and not dept_codes and not sector_ids:
            if emp and emp.department and emp.department.ntc_center_id:
                cid = emp.department.ntc_center_id
                filtered = [
                    w
                    for w in works_list
                    if w.department and w.department.ntc_center_id == cid
                ]
                return self._respond_all_depts(
                    request,
                    filtered,
                    years,
                    months_filter,
                    role_info,
                    emp,
                    today,
                )

        if sector_ids:
            if len(sector_ids) == 1:
                return self._respond_sector(
                    request,
                    sector_ids[0],
                    works_list,
                    years,
                    months_filter,
                    role_info,
                    emp,
                    today,
                )
            filtered = [w for w in works_list if w.sector_id in set(sector_ids)]
            return self._respond_all_depts(
                request,
                filtered,
                years,
                months_filter,
                role_info,
                emp,
                today,
            )

        if dept_codes:
            if len(dept_codes) == 1:
                return self._respond_dept(
                    request,
                    dept_codes[0],
                    works_list,
                    years,
                    months_filter,
                    role_info,
                    emp,
                    today,
                )
            filtered = [
                w
                for w in works_list
                if w.department and w.department.code in set(dept_codes)
            ]
            return self._respond_all_depts(
                request,
                filtered,
                years,
                months_filter,
                role_info,
                emp,
                today,
            )

        top_roles = (
            "admin",
            "ntc_head",
            "ntc_deputy",
            "chief_designer",
            "deputy_gd_econ",
        )
        if role in top_roles and not dept_codes and not center_ids:
            return self._respond_all_centers(
                request,
                works_list,
                years,
                months_filter,
                role_info,
                emp,
                today,
            )

        if center_ids and len(center_ids) == 1:
            cid = center_ids[0]
            filtered = [
                w
                for w in works_list
                if w.department and w.department.ntc_center_id == cid
            ]
            center_obj = NTCCenter.objects.filter(pk=cid).first()
            center_info = (
                {"id": cid, "code": center_obj.code, "name": center_obj.name}
                if center_obj
                else None
            )
            return self._respond_all_depts(
                request,
                filtered,
                years,
                months_filter,
                role_info,
                emp,
                today,
                center_info=center_info,
            )

        return self._respond_all_depts(
            request,
            works_list,
            years,
            months_filter,
            role_info,
            emp,
            today,
        )

    # ── Все центры ──────────────────────────────────────────────────────

    def _respond_all_centers(
        self,
        request,
        works,
        years,
        months_filter,
        role_info,
        emp,
        today,
    ):
        centers_db = {c.pk: c for c in NTCCenter.objects.all()}
        center_works = defaultdict(list)
        for w in works:
            cid = w.department.ntc_center_id if w.department else 0
            if cid:
                center_works[cid].append(w)

        centers_data = []
        for cid, cworks in sorted(center_works.items()):
            c = centers_db.get(cid)
            metrics = _build_report_metrics(cworks, years, months_filter, today)
            centers_data.append(
                {
                    "id": cid,
                    "code": c.code if c else f"Центр {cid}",
                    "name": c.name if c else "",
                    **metrics,
                }
            )

        total_metrics = _build_report_metrics(works, years, months_filter, today)
        projects = _build_project_breakdown(works, years, months_filter, today)

        return Response(
            {
                "view": "centers",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "centers": centers_data,
                "projects": projects,
                **total_metrics,
                **self._nav_context(works, role_info, emp, years),
            }
        )

    # ── Все отделы ──────────────────────────────────────────────────────

    def _respond_all_depts(
        self,
        request,
        works,
        years,
        months_filter,
        role_info,
        emp,
        today,
        center_info=None,
    ):
        dept_map = defaultdict(list)
        for w in works:
            code = w.department.code if w.department else "—"
            dept_map[code].append(w)

        dept_names = {}
        for d in Department.objects.all():
            dept_names[d.code] = d.name

        depts_data = []
        for code in sorted(dept_map.keys()):
            metrics = _build_report_metrics(dept_map[code], years, months_filter, today)
            if metrics["total"] == 0:
                continue
            depts_data.append(
                {
                    "code": code,
                    "name": dept_names.get(code, code),
                    **metrics,
                }
            )

        total_metrics = _build_report_metrics(works, years, months_filter, today)
        projects = _build_project_breakdown(works, years, months_filter, today)

        result = {
            "view": "all",
            "years": years,
            "months_filter": months_filter,
            "role_info": role_info,
            "depts": depts_data,
            "projects": projects,
            **total_metrics,
            **self._nav_context(works, role_info, emp, years),
        }
        if center_info:
            result["center"] = center_info
        return Response(result)

    # ── Один отдел ──────────────────────────────────────────────────────

    def _respond_dept(
        self,
        request,
        dept_code,
        works,
        years,
        months_filter,
        role_info,
        emp,
        today,
    ):
        dept = (
            Department.objects.prefetch_related("sectors")
            .filter(code=dept_code)
            .first()
        )
        dept_name = dept.name if dept else dept_code

        dept_works = [
            w for w in works if w.department and w.department.code == dept_code
        ]

        sectors_map = defaultdict(list)
        for w in dept_works:
            sectors_map[w.sector_id or 0].append(w)

        sector_names = {}
        if dept:
            for s in dept.sectors.all():
                sector_names[s.pk] = s.name or s.code

        sectors_data = []
        for s_id in sorted(sectors_map.keys()):
            metrics = _build_report_metrics(
                sectors_map[s_id],
                years,
                months_filter,
                today,
            )
            if metrics["total"] == 0:
                continue
            sectors_data.append(
                {
                    "id": s_id,
                    "name": sector_names.get(
                        s_id, "Без сектора" if s_id == 0 else f"Сектор {s_id}"
                    ),
                    **metrics,
                }
            )

        total_metrics = _build_report_metrics(dept_works, years, months_filter, today)
        projects = _build_project_breakdown(dept_works, years, months_filter, today)

        return Response(
            {
                "view": "dept",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "dept": {"code": dept_code, "name": dept_name},
                "sectors": sectors_data,
                "projects": projects,
                **total_metrics,
                **self._nav_context(works, role_info, emp, years, show_sectors=True),
            }
        )

    # ── Один сектор ─────────────────────────────────────────────────────

    def _respond_sector(
        self,
        request,
        sector_id,
        works,
        years,
        months_filter,
        role_info,
        emp,
        today,
    ):
        sector = (
            Sector.objects.filter(pk=sector_id).select_related("department").first()
        )
        sector_name = (sector.name or sector.code) if sector else "—"

        # Собираем сотрудников сектора
        sector_works = [w for w in works if w.sector_id == sector_id or (not sector_id)]
        emp_works_map = defaultdict(list)
        seen = set()
        for w in sector_works:
            if w.executor_id:
                e = w.executor
                if e and (not sector_id or e.sector_id == sector_id):
                    key = (e.pk, w.pk)
                    if key not in seen:
                        seen.add(key)
                        emp_works_map[e.pk].append(w)
            for te in getattr(w, "_prefetched_executors", []):
                if te.executor_id:
                    key = (te.executor_id, w.pk)
                    if key not in seen:
                        seen.add(key)
                        emp_works_map[te.executor_id].append(w)

        # Получаем имена сотрудников
        emp_names = {}
        for e in Employee.objects.filter(pk__in=emp_works_map.keys()):
            emp_names[e.pk] = e.short_name

        employees_data = []
        for e_id in sorted(emp_works_map.keys(), key=lambda x: emp_names.get(x, "")):
            report = _build_employee_report(
                e_id,
                emp_works_map[e_id],
                years,
                months_filter,
                today,
            )
            if report["total"] == 0:
                continue
            employees_data.append(
                {
                    "id": e_id,
                    "name": emp_names.get(e_id, f"Сотрудник {e_id}"),
                    **report,
                }
            )

        total_metrics = _build_report_metrics(sector_works, years, months_filter, today)

        return Response(
            {
                "view": "sector",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "sector": {"id": sector_id, "name": sector_name},
                "employees": employees_data,
                **total_metrics,
                **self._nav_context(works, role_info, emp, years),
            }
        )

    # ── Один сотрудник ──────────────────────────────────────────────────

    def _respond_employee(
        self,
        request,
        executor_id,
        works,
        years,
        months_filter,
        role_info,
        emp,
        today,
    ):
        target = (
            Employee.objects.filter(pk=executor_id)
            .select_related("department", "sector")
            .first()
        )
        if not target:
            return Response({"error": "Сотрудник не найден"}, status=404)

        emp_works = [
            w
            for w in works
            if w.executor_id == executor_id
            or any(
                te.executor_id == executor_id
                for te in getattr(w, "_prefetched_executors", [])
            )
        ]

        report = _build_employee_report(
            executor_id,
            emp_works,
            years,
            months_filter,
            today,
        )

        return Response(
            {
                "view": "employee",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "employee": {
                    "id": target.pk,
                    "name": target.short_name,
                    "dept": target.department.code if target.department else "",
                    "sector": (
                        (target.sector.name or target.sector.code)
                        if target.sector
                        else ""
                    ),
                },
                **report,
                **self._nav_context(works, role_info, emp, years),
            }
        )

    # ── Навигация (фильтр-чипы) ────────────────────────────────────────

    def _nav_context(self, works, role_info, emp, years, show_sectors=False):
        nav = {}
        role = role_info["role"]

        center_roles = (
            "admin",
            "ntc_head",
            "ntc_deputy",
            "chief_designer",
            "deputy_gd_econ",
        )
        if role in center_roles:
            nav["nav_centers"] = [
                {"id": c.pk, "code": c.code, "name": c.name or c.code}
                for c in NTCCenter.objects.order_by("code")
            ]

        if role in center_roles:
            dept_set = {}
            for w in works:
                if w.department and w.department.code not in dept_set:
                    dept_set[w.department.code] = {
                        "code": w.department.code,
                        "center_id": w.department.ntc_center_id,
                    }
            nav["nav_depts"] = [dept_set[c] for c in sorted(dept_set.keys())]

        if show_sectors or role in ("dept_head", "dept_deputy"):
            sectors_set = {}
            for w in works:
                if w.sector_id and w.sector:
                    sectors_set[w.sector_id] = w.sector.name or w.sector.code
            nav["nav_sectors"] = [
                {"id": sid, "name": sname}
                for sid, sname in sorted(sectors_set.items(), key=lambda x: x[1])
            ]

        proj_qs = Project.objects.only("pk", "name_short", "name_full")
        if role != "admin":
            proj_qs = proj_qs.filter(is_hidden=False)
        nav["nav_projects"] = [
            {"id": p.pk, "name": p.name}
            for p in proj_qs.order_by("name_short", "name_full")
        ]

        product_qs = ProjectProduct.objects.only("pk", "name", "name_short")
        if role != "admin":
            product_qs = product_qs.filter(project__is_hidden=False)
        nav["nav_products"] = [
            {"id": p.pk, "name": p.name_short or p.name}
            for p in product_qs.order_by("name")
        ]

        return nav
