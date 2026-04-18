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

from django.db.models import Exists, OuterRef, Prefetch, Q, Subquery
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.utils import get_visibility_filter
from apps.employees.models import Department, Employee, NTCCenter, Sector
from apps.works.models import (
    Project,
    ProjectProduct,
    TaskExecutor,
    Work,
    WorkCalendar,
    WorkReport,
)

from .analytics_plan import _get_role_info, _int_list_param, _str_list_param
from .month_snapshot import classify_work_for_month


def _get_calendar_norm_total(years, months_filter):
    """Сумма часов из производственного календаря за период (для одного человека)."""
    norms = {}
    for wc in WorkCalendar.objects.filter(year__in=years):
        norms.setdefault(wc.year, {})[wc.month] = float(wc.hours_norm)
    total = 0.0
    months_set = set(months_filter) if months_filter else None
    for y in years:
        for m in range(1, 13):
            if months_set and m not in months_set:
                continue
            total += norms.get(y, {}).get(m, 0)
    return round(total, 2)


def _staff_count_by_center(center_id):
    """Количество штатных сотрудников центра."""
    return Employee.objects.filter(department__ntc_center_id=center_id).count()


def _staff_count_by_dept(dept_code):
    """Количество штатных сотрудников отдела."""
    return Employee.objects.filter(department__code=dept_code).count()


def _staff_count_by_sector(sector_id):
    """Количество штатных сотрудников сектора."""
    if not sector_id:
        return 0
    return Employee.objects.filter(sector_id=sector_id).count()


def _total_staff_count(works):
    """Количество штатных сотрудников по всем отделам, задействованным в works."""
    dept_ids = set()
    for w in works:
        if w.department_id:
            dept_ids.add(w.department_id)
    if not dept_ids:
        return 0
    return Employee.objects.filter(department_id__in=dept_ids).count()


def _period_start(years, months_filter):
    """Начало отчётного периода: первый день минимального выбранного месяца/года."""
    y = min(years)
    m = min(months_filter) if months_filter else 1
    return date(y, m, 1)


def _period_end(years, months_filter):
    """Конец отчётного периода: первый день следующего месяца после максимального."""
    y = max(years)
    m = max(months_filter) if months_filter else 12
    if m == 12:
        return date(y + 1, 1, 1)
    return date(y, m + 1, 1)


def _iter_period_months(years, months_filter):
    """Перечисляет (year, month) в периоде, раскрытом years × months_filter."""
    months = months_filter if months_filter else list(range(1, 13))
    for y in years:
        for m in months:
            yield (y, m)


def _classify_task_detailed(w, today, years, months_filter):
    """
    Возвращает детальный код снимка (done / done_early / overdue / inwork /
    debt_closed / debt_hanging / done_other / None) — агрегируя по месяцам
    периода и выбирая наиболее значимый статус.
    """
    priority = {
        "done": 0,
        "done_early": 1,
        "overdue": 2,
        "debt_closed": 3,
        "debt_hanging": 3,
        "inwork": 4,
        "unplanned": 5,
    }
    best = None
    best_code = None
    saw_any = False
    for y, m in _iter_period_months(years, months_filter):
        code = classify_work_for_month(w, y, m, today)
        if code is None:
            continue
        saw_any = True
        p = priority[code]
        if best is None or p < best:
            best = p
            best_code = code
    if not saw_any:
        if getattr(w, "_done", False):
            return "done_other"
        return None
    return best_code


def _classify_task(w, today, years, months_filter):
    """
    Упрощённый статус для совместимости: схлопывает done_early→done,
    debt_closed/hanging→debt. Возвращает:
    "done" | "overdue" | "debt" | "inwork" | "done_other" | None.
    """
    code = _classify_task_detailed(w, today, years, months_filter)
    if code in ("done", "done_early"):
        return "done"
    if code in ("debt_closed", "debt_hanging"):
        return "debt"
    return code


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
    Считает метрики выполнения для набора задач по правилам «Снимка месяца».
    Единый источник правды — classify_work_for_month(). Задачи разделяются на:
      • задачи периода (done/overdue/inwork) — имеют plan_hours в периоде;
      • долги прошлых периодов — date_end < начало периода, отчёта до начала нет.
    Возвращает dict со счётчиками и списками задач-долгов.
    """
    years_set = set(years)
    months_set = set(months_filter) if months_filter else None
    ps = _period_start(years, months_filter)

    total = 0
    done = 0  # done + done_early
    done_intime = 0
    done_early = 0
    overdue = 0
    inwork = 0
    debts_1m = 0
    debts_2_3m = 0
    debts_3plus = 0
    debts_closed = 0
    debts_hanging = 0
    unplanned = 0
    plan_hours = 0.0
    debt_tasks = []

    for w in works:
        code = _classify_task_detailed(w, today, years, months_filter)

        # Не попала в снимок ни одного месяца периода / закрыта вне периода
        if code is None or code == "done_other":
            continue

        if code in ("debt_closed", "debt_hanging"):
            # Долг по правилам снимка: date_end < начало периода, отчёта до начала нет
            effective_end = w.date_end  # без deadline-fallback — как в снимке
            total += 1
            if code == "debt_closed":
                debts_closed += 1
            else:
                debts_hanging += 1
            depth = _debt_depth(effective_end, ps) if effective_end else "3plus"
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
                    "closed": code == "debt_closed",
                }
            )
            # Долги не учитываются в plan_hours текущего периода
            continue

        # Выполнено в периоде — учитываем plan_hours, если они есть
        if code in ("done", "done_early"):
            total += 1
            done += 1
            if code == "done":
                done_intime += 1
            else:
                done_early += 1
            ph = _task_plan_hours_in_period(w, years_set, months_set)
            plan_hours += ph
            continue

        # unplanned — задача идёт в работе по датам, но нет план-часов.
        # Часы в metrics не прибавляем (их нет), но задачу учитываем отдельно.
        if code == "unplanned":
            total += 1
            unplanned += 1
            continue

        # overdue / inwork — снимок уже требует plan_hours в месяце
        total += 1
        ph = _task_plan_hours_in_period(w, years_set, months_set)
        plan_hours += ph
        if code == "overdue":
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
        "done_intime": done_intime,
        "done_early": done_early,
        "overdue": overdue,
        "inwork": inwork,
        "debts_1m": debts_1m,
        "debts_2_3m": debts_2_3m,
        "debts_3plus": debts_3plus,
        "debts_total": debts_total,
        "debts_closed": debts_closed,
        "debts_hanging": debts_hanging,
        "unplanned": unplanned,
        "debt_tasks": debt_tasks[:50],  # Топ-50 долгов
        "debt_tasks_total": len(debt_tasks),
        "plan_hours": round(plan_hours, 1),
        "completion_pct": completion_pct,
    }


def _build_debts_by_units(works, years, months_filter, today, group_by="center"):
    """
    Группировка долгов по подразделениям.
    group_by: 'center' | 'dept' | 'sector'
    Возвращает список: [{code, name, debts_total, debts_1m, debts_2_3m, debts_3plus}]
    """
    ps = _period_start(years, months_filter)
    units = defaultdict(lambda: {"debts_1m": 0, "debts_2_3m": 0, "debts_3plus": 0})

    for w in works:
        status = _classify_task(w, today, years, months_filter)
        if status != "debt":
            continue
        effective_end = w.date_end  # без deadline-fallback (правила снимка)
        if not effective_end:
            continue
        depth = _debt_depth(effective_end, ps)

        if group_by == "center":
            uid = w.department.ntc_center_id if w.department else 0
            uname = ""
            if w.department and w.department.ntc_center:
                uname = w.department.ntc_center.code or ""
        elif group_by == "dept":
            uid = w.department.code if w.department else "—"
            uname = uid
        else:  # sector
            uid = w.sector_id or 0
            uname = (w.sector.name or w.sector.code) if w.sector else "Без сектора"

        bucket = units[uid]
        bucket["id"] = uid
        bucket["name"] = uname
        bucket[f"debts_{depth}"] = bucket.get(f"debts_{depth}", 0) + 1

    result = []
    for uid, data in sorted(units.items(), key=lambda x: x[0]):
        total = data["debts_1m"] + data["debts_2_3m"] + data["debts_3plus"]
        if total == 0:
            continue
        result.append(
            {
                "id": data.get("id", uid),
                "name": data.get("name", str(uid)),
                "debts_total": total,
                "debts_1m": data["debts_1m"],
                "debts_2_3m": data["debts_2_3m"],
                "debts_3plus": data["debts_3plus"],
            }
        )
    return result


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
        for k, v in ph_raw.items():
            try:
                y_str, m_str = k.split("-")
                y_int, m_int = int(y_str), int(m_str)
                if y_int in years_set and (not months_set or m_int in months_set):
                    val = float(v) if v else 0
                    ph_filtered += val
            except (ValueError, TypeError):
                pass
        ph_filtered = round(ph_filtered, 2)

        status = _classify_task(w, today, years, months_filter)

        # Не попала в снимок периода / закрыта вне периода
        if status is None or status == "done_other":
            continue

        effective_end = w.date_end  # без deadline-fallback (правила снимка)
        days_overdue = 0
        if status in ("overdue", "debt") and effective_end:
            days_overdue = (today - effective_end).days

        total += 1
        # Долги не учитываются в plan_hours текущего периода
        if status != "debt":
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
        # Дата первого заполненного отчёта (для привязки к периоду)
        first_report_created = Subquery(
            WorkReport.objects.filter(work=OuterRef("pk"))
            .order_by("created_at")
            .values("created_at")[:1]
        )

        base = (
            Work.objects.filter(vis_q, show_in_plan=True)
            .annotate(
                _done=has_reports,
                _report_created_at=first_report_created,
                _first_report_date=first_report_created,
            )
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

        # Сужаем queryset под правила снимка:
        #   а) задачи с plan_hours на любой из выбранных месяцев → кандидаты «задачи периода»;
        #   б) задачи с date_end < начала периода → кандидаты «долги».
        period_start = _period_start(years, months_filter)
        plan_q = Q()
        for y, m in _iter_period_months(years, months_filter):
            plan_q |= Q(plan_hours__has_key=f"{y:04d}-{m:02d}")
        base = base.filter(plan_q | Q(date_end__lt=period_start))

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

        # ── Фильтры (drill-down) ──────────────────────────────────────
        # Все кроме user могут смотреть любые подразделения.
        # user ограничен своим центром (visibility_filter уже фильтрует).

        if executor_ids:
            eid_set = set(executor_ids)
            filtered = [
                w
                for w in works_list
                if w.executor_id in eid_set
                or any(
                    te.executor_id in eid_set
                    for te in getattr(w, "_prefetched_executors", [])
                )
            ]
            if len(executor_ids) == 1:
                return self._respond_employee(
                    request,
                    executor_ids[0],
                    filtered,
                    years,
                    months_filter,
                    role_info,
                    emp,
                    today,
                )
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

        # ── Стартовые экраны по ролям (без фильтров) ──────────────────
        # user → свои задачи
        if role == "user":
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

        # sector_head → свой сектор (сотрудники)
        if role == "sector_head":
            sid = emp.sector_id if emp else None
            if sid:
                return self._respond_sector(
                    request,
                    sid,
                    works_list,
                    years,
                    months_filter,
                    role_info,
                    emp,
                    today,
                )

        # dept_head/dept_deputy → свой отдел (секторы)
        if role in ("dept_head", "dept_deputy"):
            if emp and emp.department:
                return self._respond_dept(
                    request,
                    emp.department.code,
                    works_list,
                    years,
                    months_filter,
                    role_info,
                    emp,
                    today,
                )

        # ntc_head/ntc_deputy → свой центр (отделы)
        if role in ("ntc_head", "ntc_deputy"):
            if emp and emp.department and emp.department.ntc_center_id:
                cid = emp.department.ntc_center_id
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

        # admin/chief_designer/deputy_gd_econ → все центры
        return self._respond_all_centers(
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
        total_metrics.pop("debt_tasks", None)
        total_metrics.pop("debt_tasks_total", None)
        projects = _build_project_breakdown(works, years, months_filter, today)
        debts_units = _build_debts_by_units(
            works, years, months_filter, today, group_by="center"
        )

        # Норма = календарные часы * штатная численность
        norm_per_person = _get_calendar_norm_total(years, months_filter)
        total_staff = _total_staff_count(works)
        total_metrics["norm_hours"] = round(norm_per_person * total_staff, 1)
        total_metrics["employee_count"] = total_staff

        # Норма и кол-во сотрудников для каждого центра
        for cd in centers_data:
            cid = cd["id"]
            ec = _staff_count_by_center(cid)
            cd["employee_count"] = ec
            cd["norm_hours"] = round(norm_per_person * ec, 1)

        return Response(
            {
                "view": "centers",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "centers": centers_data,
                "projects": projects,
                "debts_by_units": debts_units,
                "debts_group": "center",
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
        total_metrics.pop("debt_tasks", None)
        total_metrics.pop("debt_tasks_total", None)
        projects = _build_project_breakdown(works, years, months_filter, today)
        debts_units = _build_debts_by_units(
            works, years, months_filter, today, group_by="dept"
        )

        norm_per_person = _get_calendar_norm_total(years, months_filter)
        total_staff = _total_staff_count(works)
        total_metrics["norm_hours"] = round(norm_per_person * total_staff, 1)
        total_metrics["employee_count"] = total_staff

        for dd in depts_data:
            ec = _staff_count_by_dept(dd["code"])
            dd["employee_count"] = ec
            dd["norm_hours"] = round(norm_per_person * ec, 1)

        result = {
            "view": "all",
            "years": years,
            "months_filter": months_filter,
            "role_info": role_info,
            "depts": depts_data,
            "projects": projects,
            "debts_by_units": debts_units,
            "debts_group": "dept",
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
        debts_units = _build_debts_by_units(
            dept_works, years, months_filter, today, group_by="sector"
        )

        norm_per_person = _get_calendar_norm_total(years, months_filter)
        dept_staff = _staff_count_by_dept(dept_code)
        total_metrics["norm_hours"] = round(norm_per_person * dept_staff, 1)
        total_metrics["employee_count"] = dept_staff

        for sd in sectors_data:
            ec = _staff_count_by_sector(sd["id"])
            sd["employee_count"] = ec
            sd["norm_hours"] = round(norm_per_person * ec, 1)

        return Response(
            {
                "view": "dept",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "dept": {"code": dept_code, "name": dept_name},
                "sectors": sectors_data,
                "projects": projects,
                "debts_by_units": debts_units,
                "debts_group": "sector",
                **total_metrics,
                **self._nav_context(
                    works,
                    role_info,
                    emp,
                    years,
                    show_sectors=True,
                    current_dept_code=dept_code,
                ),
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

        norm_per_person = _get_calendar_norm_total(years, months_filter)
        sector_staff = _staff_count_by_sector(sector_id)
        total_metrics["norm_hours"] = round(norm_per_person * sector_staff, 1)
        total_metrics["employee_count"] = sector_staff

        for ed in employees_data:
            ed["norm_hours"] = norm_per_person

        return Response(
            {
                "view": "sector",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "sector": {"id": sector_id, "name": sector_name},
                "employees": employees_data,
                **total_metrics,
                **self._nav_context(
                    works,
                    role_info,
                    emp,
                    years,
                    show_sectors=True,
                    current_dept_code=(
                        sector.department.code if sector and sector.department else None
                    ),
                ),
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
        report["norm_hours"] = _get_calendar_norm_total(years, months_filter)

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

    def _nav_context(
        self, works, role_info, emp, years, show_sectors=False, current_dept_code=None
    ):
        nav = {}
        role = role_info["role"]

        top_global = ("admin", "chief_designer", "deputy_gd_econ")
        center_roles = top_global + ("ntc_head", "ntc_deputy")

        # Центры: top_global → все; ntc_head/ntc_deputy → не показываем (видит только свой)
        if role in top_global:
            nav["nav_centers"] = [
                {"id": c.pk, "code": c.code, "name": c.name or c.code}
                for c in NTCCenter.objects.order_by("code")
            ]

        # Отделы: top_global → все; ntc_head/ntc_deputy → только своего центра
        if role in center_roles:
            own_center_id = (
                emp.department.ntc_center_id if emp and emp.department else None
            )
            dept_set = {}
            for w in works:
                if w.department and w.department.code not in dept_set:
                    if role in ("ntc_head", "ntc_deputy") and own_center_id:
                        if w.department.ntc_center_id != own_center_id:
                            continue
                    dept_set[w.department.code] = {
                        "code": w.department.code,
                        "center_id": w.department.ntc_center_id,
                    }
            nav["nav_depts"] = [dept_set[c] for c in sorted(dept_set.keys())]

        if show_sectors or role in ("dept_head", "dept_deputy"):
            # dept_head/dept_deputy → только секторы своего отдела
            own_dept_code = emp.department.code if emp and emp.department else None
            # При drill-down в конкретный отдел — сектора только этого отдела
            restrict_dept = current_dept_code
            if role in ("dept_head", "dept_deputy") and own_dept_code:
                restrict_dept = own_dept_code
            sectors_set = {}
            for w in works:
                if w.sector_id and w.sector:
                    if restrict_dept:
                        if not w.department or w.department.code != restrict_dept:
                            continue
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
