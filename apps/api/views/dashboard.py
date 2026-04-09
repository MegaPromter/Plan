"""
API Dashboard — личный план сотрудника / сводка для руководителя.

Оптимизировано: KPI через SQL-агрегации, задачи грузятся лениво.

GET /api/dashboard/?year=2026&month=3          — лёгкий: KPI + team structure
GET /api/dashboard/scope/?year=2026&month=3&type=tasks  — задачи/долги/done_late
GET /api/dashboard/employee/<id>/?year=2026&month=3     — задачи сотрудника
"""

import calendar as cal_mod
import csv
import io
from collections import defaultdict
from datetime import date

from django.db.models import (
    BooleanField,
    Case,
    Count,
    Exists,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Value,
    When,
)
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views import View

from apps.api.mixins import LoginRequiredJsonMixin
from apps.api.utils import get_visibility_filter
from apps.employees.models import Employee
from apps.works.models import TaskExecutor, Work, WorkCalendar, WorkReport

from .analytics_plan import _get_absences, _get_calendar_norms

# ---------------------------------------------------------------------------
#  Утилиты
# ---------------------------------------------------------------------------


def _int_param(request, name, default):
    try:
        return int(request.GET.get(name, default))
    except (ValueError, TypeError):
        return default


def _year_filter(year):
    """Q-фильтр: задачи, попадающие в год."""
    return (
        Q(date_start__year__lte=year, date_end__year__gte=year)
        | Q(date_start__year=year)
        | Q(date_end__year=year)
        | Q(date_start__isnull=True, date_end__isnull=True)
        | Q(date_start__isnull=True, date_end__year=year)
        | Q(date_start__year=year, date_end__isnull=True)
    )


def _month_overlap(year, month):
    """Q-фильтр: задачи, пересекающиеся с заданным месяцем."""
    m_start = date(year, month, 1)
    m_end = date(year, month, cal_mod.monthrange(year, month)[1])
    return Q(date_end__gte=m_start, date_start__lte=m_end)


def _team_ids_for_role(emp):
    """Возвращает queryset ID сотрудников, видимых руководителю."""
    if emp.role in ("admin", "ntc_head", "ntc_deputy"):
        return Employee.objects.filter(is_active=True).values_list("pk", flat=True)
    elif emp.role in ("dept_head", "dept_deputy"):
        return Employee.objects.filter(
            is_active=True, department=emp.department
        ).values_list("pk", flat=True)
    elif emp.role == "sector_head":
        return Employee.objects.filter(is_active=True, sector=emp.sector).values_list(
            "pk", flat=True
        )
    return Employee.objects.none().values_list("pk", flat=True)


def _base_plan_qs(user, year):
    """Лёгкий базовый queryset (без select_related/prefetch)."""
    vis_q = get_visibility_filter(user)
    return Work.objects.filter(vis_q, show_in_plan=True).filter(_year_filter(year))


def _annotated_qs(qs):
    """Добавляет аннотации _done и _report_date."""
    has_reports = Exists(WorkReport.objects.filter(work=OuterRef("pk")))
    first_report_date = Subquery(
        WorkReport.objects.filter(work=OuterRef("pk"))
        .order_by("created_at")
        .values("created_at")[:1]
    )
    return qs.annotate(_done=has_reports, _report_date=first_report_date)


def _full_qs(user, year):
    """Полный queryset с select_related для сериализации задач."""
    qs = _annotated_qs(_base_plan_qs(user, year))
    te_qs = TaskExecutor.objects.select_related("executor")
    return qs.select_related(
        "department",
        "sector",
        "executor",
        "project",
        "pp_project",
        "pp_project__up_project",
    ).prefetch_related(
        Prefetch("task_executors", queryset=te_qs, to_attr="_prefetched_executors")
    )


def _executor_in_team(w, team_ids_set):
    """Проверяет, есть ли хоть один исполнитель задачи в team_ids_set."""
    if w.executor_id and w.executor_id in team_ids_set:
        return True
    for te in getattr(w, "_prefetched_executors", []):
        if te.executor_id in team_ids_set:
            return True
    return False


# ---------------------------------------------------------------------------
#  SQL-агрегации для KPI (без загрузки объектов в память)
# ---------------------------------------------------------------------------


def _compute_kpi_sql(user, year, month, team_ids_set, month_norm):
    """Считает KPI через SQL COUNT/агрегации. Возвращает dict."""
    today = timezone.now().date()
    m_start = date(year, month, 1)
    m_end = date(year, month, cal_mod.monthrange(year, month)[1])

    base = _base_plan_qs(user, year)

    # Фильтр: задачи, где исполнитель в команде
    team_q = Q(executor_id__in=team_ids_set) | Q(
        task_executors__executor_id__in=team_ids_set
    )

    team_base = base.filter(team_q).distinct()

    # Аннотируем статусы
    has_reports = Exists(WorkReport.objects.filter(work=OuterRef("pk")))
    first_report = Subquery(
        WorkReport.objects.filter(work=OuterRef("pk"))
        .order_by("created_at")
        .values("created_at")[:1]
    )

    annotated = team_base.annotate(
        _done=has_reports,
        _report_date=first_report,
        _is_overdue=Case(
            When(
                _done=False,
                date_end__lt=today,
                date_end__isnull=False,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
        _in_month=Case(
            When(
                date_end__gte=m_start,
                date_start__lte=m_end,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
    )

    # Один SQL-запрос для всех counts
    counts = annotated.aggregate(
        done_in_month=Count("pk", filter=Q(_done=True, _in_month=True)),
        inwork_in_month=Count(
            "pk", filter=Q(_done=False, _is_overdue=False, _in_month=True)
        ),
        total_debts=Count("pk", filter=Q(_is_overdue=True)),
        total_done=Count("pk", filter=Q(_done=True)),
    )

    # done_on_time: сравнение _report_date с date_end —
    # сложно через Django ORM 3.2, считаем через отдельный запрос
    done_with_dates = annotated.filter(_done=True, date_end__isnull=False).values_list(
        "date_end", "_report_date"
    )

    total_done_count = 0
    done_on_time_count = 0
    done_late_count = 0
    overdue_days_sum = 0
    overdue_days_cnt = 0

    for d_end, r_date in done_with_dates:
        total_done_count += 1
        if r_date:
            rd = r_date.date() if hasattr(r_date, "date") else r_date
            if rd <= d_end:
                done_on_time_count += 1
            else:
                done_late_count += 1
        else:
            done_on_time_count += 1

    # avg_overdue — среднее количество дней просрочки для долгов
    overdue_dates = annotated.filter(_is_overdue=True).values_list(
        "date_end", flat=True
    )
    for d_end in overdue_dates:
        if d_end:
            overdue_days_sum += (today - d_end).days
            overdue_days_cnt += 1

    on_time_pct = (
        round(done_on_time_count / total_done_count * 100, 1)
        if total_done_count > 0
        else -1
    )
    avg_overdue = (
        round(overdue_days_sum / overdue_days_cnt, 1) if overdue_days_cnt > 0 else 0
    )

    return {
        "done_count": counts["done_in_month"] or 0,
        "inwork_count": counts["inwork_in_month"] or 0,
        "total_debts": counts["total_debts"] or 0,
        "overdue_count": 0,
        "done_late_count": done_late_count,
        "on_time_pct": on_time_pct,
        "avg_overdue_days": avg_overdue,
        "total_done": total_done_count,
    }


# ---------------------------------------------------------------------------
#  Подсчёт plan_hours через values_list (лёгкий — только JSON-поле)
# ---------------------------------------------------------------------------


def _compute_hours(user, year, month, team_ids_set, month_norm):
    """Считает плановые часы через values_list (без загрузки полных объектов).

    Возвращает (scope_planned, scope_load, emp_hours, emp_monthly).
    emp_hours = {eid: hours_this_month}
    emp_monthly = {eid: {month_int: hours}}
    """
    month_key = f"{year}-{month:02d}"
    base = _base_plan_qs(user, year)

    # Часы основных исполнителей
    emp_hours = defaultdict(float)
    emp_monthly = defaultdict(lambda: defaultdict(float))

    # 1) Work.plan_hours + executor_id — основной исполнитель
    main_data = base.filter(executor_id__in=team_ids_set).values_list(
        "executor_id", "plan_hours"
    )
    for eid, ph in main_data:
        if not ph:
            continue
        for k, v in ph.items():
            try:
                y_str, m_str = k.split("-")
                if int(y_str) == year:
                    hrs = float(v) if v else 0
                    emp_monthly[eid][int(m_str)] += hrs
                    if k == month_key:
                        emp_hours[eid] += hrs
            except (ValueError, TypeError):
                pass

    # 2) TaskExecutor.plan_hours — дополнительные исполнители
    te_data = TaskExecutor.objects.filter(
        work__in=base,
        executor_id__in=team_ids_set,
    ).values_list("executor_id", "plan_hours")
    for eid, ph in te_data:
        if not ph:
            continue
        for k, v in ph.items():
            try:
                y_str, m_str = k.split("-")
                if int(y_str) == year:
                    hrs = float(v) if v else 0
                    emp_monthly[eid][int(m_str)] += hrs
                    if k == month_key:
                        emp_hours[eid] += hrs
            except (ValueError, TypeError):
                pass

    scope_planned = round(sum(emp_hours.values()), 1)
    team_count = len(team_ids_set)
    scope_norm = round(month_norm * team_count, 1) if month_norm else 0
    scope_load = round(scope_planned / scope_norm * 100, 1) if scope_norm > 0 else 0

    return scope_planned, scope_load, scope_norm, emp_hours, emp_monthly


# ---------------------------------------------------------------------------
#  Team structure (employee metrics через SQL annotate)
# ---------------------------------------------------------------------------


def _build_team_structure(emp, team_ids_set, emp_hours, month_norm):
    """Строит иерархию отдел → сектор → сотрудники (только метрики, без задач)."""
    _emp_only = (
        "id",
        "last_name",
        "first_name",
        "patronymic",
        "department_id",
        "sector_id",
        "department__id",
        "department__code",
        "department__name",
        "sector__id",
        "sector__code",
        "sector__name",
    )

    if emp.role in ("admin", "ntc_head", "ntc_deputy"):
        qs = Employee.objects.filter(is_active=True)
    elif emp.role in ("dept_head", "dept_deputy"):
        qs = Employee.objects.filter(is_active=True, department=emp.department)
    elif emp.role == "sector_head":
        qs = Employee.objects.filter(is_active=True, sector=emp.sector)
    else:
        return None

    team_employees = list(
        qs.select_related("department", "sector").only(*_emp_only).exclude(pk=emp.pk)
    )

    if not team_employees:
        return None

    # Считаем overdue_count/done_count/inwork_count для каждого сотрудника
    # через emp_debts_count (из KPI SQL) — но нам нужны per-employee counts.
    # Вместо загрузки всех задач, возьмём counts через SQL.
    today = timezone.now().date()

    # Per-employee overdue counts через SQL
    emp_overdue_counts = dict(
        Work.objects.filter(
            show_in_plan=True,
            date_end__lt=today,
            date_end__isnull=False,
        )
        .exclude(pk__in=WorkReport.objects.values("work_id"))
        .filter(Q(executor_id__in=team_ids_set))
        .values("executor_id")
        .annotate(cnt=Count("pk"))
        .values_list("executor_id", "cnt")
    )

    # Также для TaskExecutor
    te_overdue = dict(
        TaskExecutor.objects.filter(
            executor_id__in=team_ids_set,
            work__show_in_plan=True,
            work__date_end__lt=today,
            work__date_end__isnull=False,
        )
        .exclude(work__pk__in=WorkReport.objects.values("work_id"))
        .values("executor_id")
        .annotate(cnt=Count("work_id", distinct=True))
        .values_list("executor_id", "cnt")
    )

    dept_sectors = defaultdict(lambda: defaultdict(list))
    total_load_sum = 0
    total_overdue = 0
    total_count = 0

    for e in team_employees:
        planned = round(emp_hours.get(e.pk, 0), 1)
        load = round(planned / month_norm * 100, 1) if month_norm > 0 else 0
        ov = emp_overdue_counts.get(e.pk, 0) + te_overdue.get(e.pk, 0)

        emp_item = {
            "id": e.pk,
            "name": e.short_name,
            "planned": planned,
            "load_pct": load,
            "done_count": 0,  # Считается на клиенте при раскрытии
            "overdue_count": ov,
            "inwork_count": 0,  # Считается на клиенте при раскрытии
        }
        total_load_sum += load
        total_overdue += ov
        total_count += 1

        dept_code = e.department.code if e.department else "—"
        dept_name = e.department.name if e.department else ""
        sector_key = (e.sector.name or e.sector.code) if e.sector else ""
        dept_sectors[(dept_code, dept_name)][sector_key].append(emp_item)

    DEPT_ORDER = [
        "021",
        "022",
        "024",
        "027",
        "028",
        "029",
        "301",
        "082",
        "084",
        "086",
    ]

    def _dept_sort_key(item):
        code = item[0][0]
        try:
            return DEPT_ORDER.index(code)
        except ValueError:
            return len(DEPT_ORDER)

    departments = []
    for (dept_code, dept_name), sectors_dict in sorted(
        dept_sectors.items(), key=_dept_sort_key
    ):
        dept_load_sum = 0
        dept_overdue = 0
        dept_count = 0

        sector_list = []
        for sector_name, emps in sorted(sectors_dict.items(), key=lambda x: x[0]):
            emps.sort(key=lambda x: (-x["overdue_count"], -x["load_pct"]))
            s_load_sum = sum(e["load_pct"] for e in emps)
            s_overdue = sum(e["overdue_count"] for e in emps)
            s_count = len(emps)

            sector_list.append(
                {
                    "name": sector_name or "(без сектора)",
                    "count": s_count,
                    "planned": round(sum(e["planned"] for e in emps), 1),
                    "avg_load_pct": round(s_load_sum / s_count, 1) if s_count else 0,
                    "overdue_count": s_overdue,
                    "employees": emps,
                }
            )
            dept_load_sum += s_load_sum
            dept_overdue += s_overdue
            dept_count += s_count

        departments.append(
            {
                "code": dept_code,
                "name": dept_name,
                "count": dept_count,
                "planned": round(sum(s["planned"] for s in sector_list), 1),
                "avg_load_pct": (
                    round(dept_load_sum / dept_count, 1) if dept_count else 0
                ),
                "overdue_count": dept_overdue,
                "sectors": sector_list,
            }
        )

    avg_load = round(total_load_sum / total_count, 1) if total_count else 0

    return {
        "total_employees": total_count,
        "avg_load_pct": avg_load,
        "total_overdue": total_overdue,
        "departments": departments,
    }


# ---------------------------------------------------------------------------
#  Сериализация задачи
# ---------------------------------------------------------------------------


def _serialize_task(w, ph, status, today, year):
    executor_name = ""
    if w.executor:
        executor_name = w.executor.short_name
    project_name = (
        w.project.name
        if w.project
        else (
            w.pp_project.up_project.name
            if w.pp_project and w.pp_project.up_project
            else (w.pp_project.name if w.pp_project else "")
        )
    )
    item = {
        "id": w.id,
        "work_name": w.work_name or w.work_num or "",
        "work_designation": w.work_designation or "",
        "project_name": project_name,
        "project_sort": project_name.lower() if project_name else "",
        "executor_name": executor_name,
        "date_start": w.date_start.isoformat() if w.date_start else "",
        "date_end": w.date_end.isoformat() if w.date_end else "",
        "status": status,
    }
    if status == "overdue" and w.date_end:
        item["days_overdue"] = (today - w.date_end).days
    elif status == "inwork" and w.date_end:
        item["days_left"] = (w.date_end - today).days
    if status == "done":
        rd = getattr(w, "_report_date", None)
        if rd and w.date_end:
            rd_date = rd.date() if hasattr(rd, "date") else rd
            if rd_date > w.date_end:
                item["days_late"] = (rd_date - w.date_end).days
    return item


# ---------------------------------------------------------------------------
#  GET /api/dashboard/employee/<id>/?year=2026&month=3
# ---------------------------------------------------------------------------


class DashboardEmployeeView(LoginRequiredJsonMixin, View):
    """Задачи и долги конкретного сотрудника (ленивая загрузка по клику)."""

    def get(self, request, pk):
        today = timezone.now().date()
        year = _int_param(request, "year", today.year)
        month = _int_param(request, "month", today.month)

        emp = getattr(request.user, "employee", None)
        if not emp or not emp.is_writer:
            return JsonResponse({"error": "Нет доступа"}, status=403)

        # Загружаем только задачи ЭТОГО сотрудника (не все 9000)
        month_key = f"{year}-{month:02d}"
        m_start = date(year, month, 1)
        m_end = date(year, month, cal_mod.monthrange(year, month)[1])

        emp_q = Q(executor_id=pk) | Q(task_executors__executor_id=pk)
        qs = _full_qs(request.user, year).filter(emp_q).distinct()

        tasks = []
        debts = []

        for w in qs:
            # plan_hours для этого сотрудника
            ph = {}
            if w.executor_id == pk:
                ph = w.plan_hours or {}
            else:
                for te in getattr(w, "_prefetched_executors", []):
                    if te.executor_id == pk:
                        ph = te.plan_hours or {}
                        break

            is_done = getattr(w, "_done", False)
            is_overdue = not is_done and w.date_end and w.date_end < today
            status = "done" if is_done else ("overdue" if is_overdue else "inwork")

            hrs = float(ph.get(month_key, 0) or 0)
            in_month = hrs > 0
            if not in_month and w.date_start and w.date_end:
                in_month = w.date_end >= m_start and w.date_start <= m_end

            task_item = _serialize_task(w, ph, status, today, year)

            if status == "overdue":
                debts.append(task_item)
            elif in_month:
                tasks.append(task_item)

        return JsonResponse({"tasks": tasks, "debts": debts})


# ---------------------------------------------------------------------------
#  GET /api/dashboard/scope/?year=2026&month=3&type=tasks|debts|done_late
# ---------------------------------------------------------------------------


class DashboardScopeView(LoginRequiredJsonMixin, View):
    """Ленивая загрузка scope_tasks / scope_debts / scope_done_late."""

    def get(self, request):
        today = timezone.now().date()
        year = _int_param(request, "year", today.year)
        month = _int_param(request, "month", today.month)
        scope_type = request.GET.get("type", "tasks")
        limit = _int_param(request, "limit", 200)
        offset = _int_param(request, "offset", 0)

        emp = getattr(request.user, "employee", None)
        if not emp or not emp.is_writer:
            return JsonResponse({"error": "Нет доступа"}, status=403)

        team_ids_set = set(_team_ids_for_role(emp))
        if not team_ids_set:
            return JsonResponse({"items": [], "total": 0})

        team_q = Q(executor_id__in=team_ids_set) | Q(
            task_executors__executor_id__in=team_ids_set
        )
        qs = _full_qs(request.user, year).filter(team_q).distinct()

        if scope_type == "debts":
            # Просроченные невыполненные
            qs = qs.exclude(pk__in=WorkReport.objects.values("work_id")).filter(
                date_end__lt=today, date_end__isnull=False
            )
            qs = qs.order_by("date_end")
        elif scope_type == "done_late":
            # Выполненные с просрочкой — нужно post-filter
            qs = (
                _annotated_qs(
                    _base_plan_qs(request.user, year).filter(team_q).distinct()
                )
                .filter(_done=True, date_end__isnull=False)
                .select_related(
                    "department",
                    "sector",
                    "executor",
                    "project",
                    "pp_project",
                    "pp_project__up_project",
                )
            )
            te_qs = TaskExecutor.objects.select_related("executor")
            qs = qs.prefetch_related(
                Prefetch(
                    "task_executors", queryset=te_qs, to_attr="_prefetched_executors"
                )
            )
            # Фильтруем в Python (report_date > date_end)
            items = []
            for w in qs:
                rd = getattr(w, "_report_date", None)
                if rd:
                    rd_date = rd.date() if hasattr(rd, "date") else rd
                    if rd_date > w.date_end:
                        ph = w.plan_hours or {}
                        items.append(_serialize_task(w, ph, "done", today, year))
            total = len(items)
            items = items[offset : offset + limit]
            return JsonResponse({"items": items, "total": total})
        else:
            # tasks — задачи текущего месяца (не просроченные, не done_late)
            qs = qs.filter(_month_overlap(year, month))
            qs = qs.order_by("date_end")

        total = qs.count()
        page = list(qs[offset : offset + limit])

        items = []
        for w in page:
            is_done = getattr(w, "_done", False)
            is_overdue = not is_done and w.date_end and w.date_end < today
            status = "done" if is_done else ("overdue" if is_overdue else "inwork")
            ph = w.plan_hours or {}
            items.append(_serialize_task(w, ph, status, today, year))

        return JsonResponse({"items": items, "total": total})


# ---------------------------------------------------------------------------
#  GET /api/dashboard/?year=2026&month=3  — ЛЁГКИЙ endpoint
# ---------------------------------------------------------------------------


class DashboardAPIView(LoginRequiredJsonMixin, View):
    """Лёгкий dashboard: KPI через SQL, team structure, без массивов задач."""

    def get(self, request):
        today = timezone.now().date()
        year = _int_param(request, "year", today.year)
        month = _int_param(request, "month", today.month)

        emp = getattr(request.user, "employee", None)
        if not emp:
            return JsonResponse({"error": "Сотрудник не найден"}, status=404)

        role = emp.role

        available_years = sorted(
            set(WorkCalendar.objects.values_list("year", flat=True))
        )
        if not available_years:
            available_years = [today.year]

        norms = _get_calendar_norms([year])
        month_norm = norms.get(year, {}).get(month, 0)

        absences = _get_absences(emp.pk, [year])

        result = {
            "year": year,
            "month": month,
            "available_years": available_years,
            "employee": {
                "id": emp.pk,
                "name": emp.short_name,
                "dept": emp.department.code if emp.department else "",
                "sector": (emp.sector.name or emp.sector.code) if emp.sector else "",
            },
            "role": role,
            "absences": absences,
            "team": None,
            # Задачи/долги больше НЕ в основном ответе — грузятся лениво
            "tasks": [],
            "debts": [],
            "done_late": [],
        }

        if emp.is_writer:
            team_ids_set = set(_team_ids_for_role(emp))

            # KPI через SQL (не загружает объекты)
            kpi = _compute_kpi_sql(request.user, year, month, team_ids_set, month_norm)

            # Часы через values_list (лёгкий запрос)
            scope_planned, scope_load, scope_norm, emp_hours, emp_monthly = (
                _compute_hours(request.user, year, month, team_ids_set, month_norm)
            )
            kpi["load_pct"] = scope_load
            kpi["planned_hours"] = scope_planned
            kpi["norm_hours"] = scope_norm

            result["kpi"] = kpi

            # Months overview
            result["months"] = self._build_months_overview(
                team_ids_set, emp_monthly, year, norms
            )

            # Team structure (без задач)
            result["team"] = _build_team_structure(
                emp, team_ids_set, emp_hours, month_norm
            )

            # П.6: Личные KPI руководителя («Мои задачи»)
            my_personal = self._build_personal_kpi(
                emp.pk, request.user, year, month, month_norm, today
            )
            result["my_kpi"] = my_personal["kpi"]

            # П.9: KPI предыдущего месяца (для сравнения)
            prev_month = month - 1 if month > 1 else 12
            prev_year = year if month > 1 else year - 1
            prev_norm = norms.get(prev_year, {}).get(prev_month, 0)
            if not prev_norm and prev_year != year:
                prev_norms = _get_calendar_norms([prev_year])
                prev_norm = prev_norms.get(prev_year, {}).get(prev_month, 0)
            prev_kpi = _compute_kpi_sql(
                request.user, prev_year, prev_month, team_ids_set, prev_norm
            )
            _, prev_load, prev_scope_norm, _, _ = _compute_hours(
                request.user, prev_year, prev_month, team_ids_set, prev_norm
            )
            prev_kpi["load_pct"] = prev_load
            prev_kpi["norm_hours"] = prev_scope_norm
            result["prev_kpi"] = prev_kpi
        else:
            # Обычный сотрудник — личные KPI
            personal = self._build_personal_kpi(
                emp.pk, request.user, year, month, month_norm, today
            )
            result["kpi"] = personal["kpi"]
            result["months"] = personal["months"]

        response = JsonResponse(result)
        response["Cache-Control"] = "private, max-age=10"
        return response

    def _build_personal_kpi(self, emp_id, user, year, month, month_norm, today):
        """Личный KPI для обычного сотрудника через лёгкие запросы."""
        month_key = f"{year}-{month:02d}"

        # Часы — только для этого сотрудника
        emp_hours = defaultdict(float)
        emp_monthly = defaultdict(lambda: defaultdict(float))

        base = _base_plan_qs(user, year)

        # Main executor
        for (ph,) in base.filter(executor_id=emp_id).values_list("plan_hours"):
            if not ph:
                continue
            for k, v in ph.items():
                try:
                    y_str, m_str = k.split("-")
                    if int(y_str) == year:
                        hrs = float(v) if v else 0
                        emp_monthly[emp_id][int(m_str)] += hrs
                        if k == month_key:
                            emp_hours[emp_id] += hrs
                except (ValueError, TypeError):
                    pass

        # TaskExecutor
        for (ph,) in TaskExecutor.objects.filter(
            work__in=base, executor_id=emp_id
        ).values_list("plan_hours"):
            if not ph:
                continue
            for k, v in ph.items():
                try:
                    y_str, m_str = k.split("-")
                    if int(y_str) == year:
                        hrs = float(v) if v else 0
                        emp_monthly[emp_id][int(m_str)] += hrs
                        if k == month_key:
                            emp_hours[emp_id] += hrs
                except (ValueError, TypeError):
                    pass

        planned = round(emp_hours.get(emp_id, 0), 1)
        load_pct = round(planned / month_norm * 100, 1) if month_norm > 0 else 0

        # Counts через SQL
        emp_q = Q(executor_id=emp_id) | Q(task_executors__executor_id=emp_id)
        my_base = base.filter(emp_q).distinct()

        has_reports = Exists(WorkReport.objects.filter(work=OuterRef("pk")))
        annotated = my_base.annotate(_done=has_reports)

        m_start = date(year, month, 1)
        m_end = date(year, month, cal_mod.monthrange(year, month)[1])

        counts = annotated.aggregate(
            done_in_month=Count(
                "pk",
                filter=Q(
                    _done=True,
                    date_end__gte=m_start,
                    date_start__lte=m_end,
                ),
            ),
            inwork_in_month=Count(
                "pk",
                filter=Q(
                    _done=False,
                    date_end__gte=m_start,
                    date_start__lte=m_end,
                )
                & ~Q(date_end__lt=today),
            ),
            total_debts=Count(
                "pk",
                filter=Q(_done=False, date_end__lt=today, date_end__isnull=False),
            ),
        )

        # done_late — считаем
        first_report = Subquery(
            WorkReport.objects.filter(work=OuterRef("pk"))
            .order_by("created_at")
            .values("created_at")[:1]
        )
        done_data = (
            my_base.filter(
                pk__in=WorkReport.objects.values("work_id"),
                date_end__isnull=False,
            )
            .annotate(_report_date=first_report)
            .values_list("date_end", "_report_date")
        )
        total_done = 0
        done_on_time = 0
        done_late_count = 0
        for d_end, r_date in done_data:
            total_done += 1
            if r_date:
                rd = r_date.date() if hasattr(r_date, "date") else r_date
                if rd <= d_end:
                    done_on_time += 1
                else:
                    done_late_count += 1
            else:
                done_on_time += 1

        on_time_pct = (
            round(done_on_time / total_done * 100, 1) if total_done > 0 else -1
        )

        norms = _get_calendar_norms([year])
        months = []
        for m in range(1, 13):
            m_planned = round(emp_monthly[emp_id].get(m, 0), 1)
            m_norm = norms.get(year, {}).get(m, 0)
            m_load = round(m_planned / m_norm * 100, 1) if m_norm > 0 else 0
            months.append(
                {
                    "month": m,
                    "planned": m_planned,
                    "norm": round(m_norm, 1),
                    "load_pct": m_load,
                }
            )

        return {
            "kpi": {
                "load_pct": load_pct,
                "planned_hours": planned,
                "norm_hours": round(month_norm, 1),
                "done_count": counts["done_in_month"] or 0,
                "overdue_count": 0,
                "inwork_count": counts["inwork_in_month"] or 0,
                "done_late_count": done_late_count,
                "on_time_pct": on_time_pct,
                "avg_overdue_days": 0,
                "total_debts": counts["total_debts"] or 0,
                "total_done": total_done,
            },
            "months": months,
        }

    def _build_months_overview(self, team_ids_set, emp_monthly, year, norms):
        """12 месяцев с загрузкой для чипов (scope)."""
        result = []
        for m in range(1, 13):
            m_planned = round(
                sum(emp_monthly[eid].get(m, 0) for eid in team_ids_set), 1
            )
            m_norm_val = norms.get(year, {}).get(m, 0) * len(team_ids_set)
            m_load = round(m_planned / m_norm_val * 100, 1) if m_norm_val > 0 else 0
            result.append(
                {
                    "month": m,
                    "planned": m_planned,
                    "norm": round(m_norm_val, 1),
                    "load_pct": m_load,
                }
            )
        return result


# ---------------------------------------------------------------------------
#  GET /api/dashboard/export/?year=2026&month=3&type=debts  — экспорт CSV
# ---------------------------------------------------------------------------


class DashboardExportView(LoginRequiredJsonMixin, View):
    """Экспорт задач/долгов/done_late в CSV (для совещаний)."""

    def get(self, request):
        today = timezone.now().date()
        year = _int_param(request, "year", today.year)
        month = _int_param(request, "month", today.month)
        export_type = request.GET.get("type", "debts")

        emp = getattr(request.user, "employee", None)
        if not emp or not emp.is_writer:
            return JsonResponse({"error": "Нет доступа"}, status=403)

        team_ids_set = set(_team_ids_for_role(emp))
        if not team_ids_set:
            return JsonResponse({"error": "Нет команды"}, status=400)

        team_q = Q(executor_id__in=team_ids_set) | Q(
            task_executors__executor_id__in=team_ids_set
        )
        qs = _full_qs(request.user, year).filter(team_q).distinct()

        if export_type == "debts":
            qs = (
                qs.exclude(pk__in=WorkReport.objects.values("work_id"))
                .filter(date_end__lt=today, date_end__isnull=False)
                .order_by("date_end")
            )
            title = "Долги"
        elif export_type == "done_late":
            qs = (
                _annotated_qs(
                    _base_plan_qs(request.user, year).filter(team_q).distinct()
                )
                .filter(_done=True, date_end__isnull=False)
                .select_related(
                    "department",
                    "sector",
                    "executor",
                    "project",
                    "pp_project",
                    "pp_project__up_project",
                )
            )
            title = "Выполнены с просрочкой"
        else:
            qs = qs.filter(_month_overlap(year, month)).order_by("date_end")
            title = "Задачи"

        # CSV
        buf = io.StringIO()
        # BOM для корректного открытия в Excel
        buf.write("\ufeff")
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(
            [
                "Задача",
                "Обозначение",
                "Проект",
                "Исполнитель",
                "Дата начала",
                "Дата окончания",
                "Статус",
                "Дней просрочки",
            ]
        )

        for w in qs:
            is_done = getattr(w, "_done", False)
            is_overdue = not is_done and w.date_end and w.date_end < today
            status_text = (
                "Выполнено" if is_done else ("Просрочено" if is_overdue else "В работе")
            )

            # Для done_late — фильтр по report_date > date_end
            if export_type == "done_late":
                rd = getattr(w, "_report_date", None)
                if not rd:
                    continue
                rd_date = rd.date() if hasattr(rd, "date") else rd
                if rd_date <= w.date_end:
                    continue
                days = (rd_date - w.date_end).days
            elif is_overdue and w.date_end:
                days = (today - w.date_end).days
            else:
                days = ""

            executor_name = w.executor.short_name if w.executor else ""
            project_name = (
                w.project.name
                if w.project
                else (
                    w.pp_project.up_project.name
                    if w.pp_project and w.pp_project.up_project
                    else (w.pp_project.name if w.pp_project else "")
                )
            )

            writer.writerow(
                [
                    w.work_name or w.work_num or "",
                    w.work_designation or "",
                    project_name,
                    executor_name,
                    w.date_start.isoformat() if w.date_start else "",
                    w.date_end.isoformat() if w.date_end else "",
                    status_text,
                    days,
                ]
            )

        response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="{title}_{year}-{month:02d}.csv"'
        )
        return response
