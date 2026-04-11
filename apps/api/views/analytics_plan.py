"""
API аналитики «Личный план» — иерархическая загрузка по ролям.

GET /api/analytics/plan/
    ?years=2026,2025     (через запятую; по умолчанию текущий год)
    &months=3,4          (через запятую; пусто = все)
    &project_ids=5,12    (фильтр по УП-проектам)
    &product_ids=3,7     (фильтр по изделиям)
    &dept_codes=021,022  (фильтр по отделам — drill-down / мульти-выбор)
    &sector_ids=7,8      (фильтр по секторам)
    &executor_ids=12,15  (фильтр по сотрудникам)
"""

from collections import defaultdict

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.utils import get_visibility_filter
from apps.employees.models import (
    BusinessTrip,
    Department,
    Employee,
    NTCCenter,
    Sector,
    Vacation,
)
from apps.works.models import (
    Project,
    ProjectProduct,
    TaskExecutor,
    Work,
    WorkCalendar,
    WorkReport,
)


def _float(v):
    if v is None:
        return 0.0
    return round(float(v), 2)


def _get_calendar_norms(years):
    """Возвращает {year: {month_int: hours_norm}} для списка лет."""
    norms = {}
    for wc in WorkCalendar.objects.filter(year__in=years):
        norms.setdefault(wc.year, {})[wc.month] = float(wc.hours_norm)
    return norms


def _get_role_info(emp):
    if not emp:
        return {"role": "user", "dept": "", "sector": "", "sector_id": 0, "dept_id": 0}
    return {
        "role": emp.role,
        "dept": emp.department.code if emp.department else "",
        "dept_id": emp.department_id or 0,
        "sector": (emp.sector.name or emp.sector.code) if emp.sector else "",
        "sector_id": emp.sector_id or 0,
    }


def _get_absences(employee_id, years):
    """Отпуска и командировки сотрудника за выбранные годы."""
    absences = []
    vac_type_map = {
        "annual": "Ежегодный отпуск",
        "unpaid": "Без сохранения",
        "sick": "Больничный",
        "other": "Прочее",
    }
    # Захватываем отсутствия, которые пересекаются с любым из выбранных годов
    # (включая те, что начались в предыдущем году, но заканчиваются в выбранном)
    year_q = Q()
    for y in years:
        year_q |= Q(date_start__year=y) | Q(date_end__year=y)
    for v in Vacation.objects.filter(year_q, employee_id=employee_id):
        absences.append(
            {
                "type": "vacation",
                "label": vac_type_map.get(v.vac_type, "Отпуск"),
                "date_start": v.date_start.isoformat(),
                "date_end": v.date_end.isoformat(),
            }
        )
    trip_status_ok = (
        BusinessTrip.STATUS_PLAN,
        BusinessTrip.STATUS_ACTIVE,
        BusinessTrip.STATUS_DONE,
    )
    trip_year_q = Q()
    for y in years:
        trip_year_q |= Q(date_start__year=y) | Q(date_end__year=y)
    for bt in BusinessTrip.objects.filter(
        trip_year_q,
        employee_id=employee_id,
        status__in=trip_status_ok,
    ):
        absences.append(
            {
                "type": "trip",
                "label": bt.location or "Командировка",
                "date_start": bt.date_start.isoformat(),
                "date_end": bt.date_end.isoformat(),
            }
        )
    return absences


def _build_employee_plan(emp_id, works, all_norms, years, months_filter):
    """
    Считает план для одного сотрудника.
    all_norms: {year: {month: norm}}
    years: список выбранных лет
    months_filter: список выбранных месяцев (пустой = все)
    """
    tasks = []
    monthly_hours = defaultdict(float)  # {(year, month): hours}
    years_set = set(years)
    months_filter_set = set(months_filter) if months_filter else None

    for w in works:
        ph = {}
        if w.executor_id == emp_id:
            ph = w.plan_hours or {}
        else:
            for te in getattr(w, "_prefetched_executors", []):
                if te.executor_id == emp_id:
                    ph = te.plan_hours or {}
                    break

        if not ph and w.executor_id != emp_id:
            continue

        # Фильтруем plan_hours: оставляем только выбранные годы/месяцы
        filtered_ph = {}
        has_hours_in_filter = False
        for k, v in ph.items():
            try:
                y_str, m_str = k.split("-")
                y_int, m_int = int(y_str), int(m_str)
                if y_int in years_set:
                    if not months_filter_set or m_int in months_filter_set:
                        monthly_hours[(y_int, m_int)] += float(v) if v else 0
                        filtered_ph[k] = v
                        if float(v) if v else 0:
                            has_hours_in_filter = True
            except (ValueError, TypeError):
                pass

        # Если выбран конкретный месяц — показываем только задачи с часами в нём
        if months_filter_set and not has_hours_in_filter:
            continue

        is_done = getattr(w, "_done", False)
        today = timezone.now().date()
        is_overdue = not is_done and w.date_end and w.date_end < today

        tasks.append(
            {
                "id": w.id,
                "work_name": w.work_name or w.work_num or "",
                "work_num": w.work_num or "",
                "project": (w.pp_stage.row_code if w.pp_stage_id else w.row_code) or "",
                "project_name": (
                    w.project.name
                    if w.project
                    else (
                        w.pp_project.up_project.name
                        if w.pp_project and w.pp_project.up_project
                        else (w.pp_project.name if w.pp_project else "")
                    )
                ),
                "date_start": w.date_start.isoformat() if w.date_start else "",
                "date_end": w.date_end.isoformat() if w.date_end else "",
                "deadline": (
                    (w.date_end or w.deadline).isoformat()
                    if (w.date_end or w.deadline)
                    else ""
                ),
                "labor": _float(w.labor),
                "plan_hours": {k: _float(v) for k, v in filtered_ph.items()},
                "status": (
                    "done" if is_done else ("overdue" if is_overdue else "inwork")
                ),
            }
        )

    # Суммируем по месяцам (по всем выбранным годам)
    months_data = []
    total_planned = 0.0
    total_norm = 0.0
    months_set = set(months_filter) if months_filter else None
    for m in range(1, 13):
        norm = 0.0
        for y in years:
            norm += all_norms.get(y, {}).get(m, 0)
        # Если фильтр по месяцам — невыбранные: план=0, но норма в months_data для графика
        if months_set and m not in months_set:
            months_data.append(
                {
                    "month": m,
                    "planned": 0,
                    "norm": round(norm, 2),
                    "load_pct": 0,
                    "filtered": False,
                }
            )
            continue
        # Выбранный месяц (или все, если фильтра нет)
        total_norm += norm
        planned = 0.0
        for y in years:
            planned += monthly_hours.get((y, m), 0)
        planned = round(planned, 2)
        load_pct = round(planned / norm * 100, 1) if norm > 0 else 0
        total_planned += planned
        months_data.append(
            {
                "month": m,
                "planned": planned,
                "norm": round(norm, 2),
                "load_pct": load_pct,
            }
        )

    total_load = round(total_planned / total_norm * 100, 1) if total_norm > 0 else 0
    return {
        "tasks": tasks,
        "months": months_data,
        "total_planned": round(total_planned, 2),
        "total_norm": round(total_norm, 2),
        "total_load_pct": total_load,
    }


def _build_works_summary(works, years, months_filter):
    """
    Сводка по задачам для уровня НТЦ/отдела.
    Возвращает dict с planned/overdue/done/not_done + списки задач.
    """
    today = timezone.now().date()
    years_set = set(years)
    months_set = set(months_filter) if months_filter else None

    planned = []  # Запланировано на выбранный месяц
    overdue = []  # Ранее просроченные
    done = []  # Выполнено
    not_done = []  # Не выполнено (в работе)

    for w in works:
        is_done = getattr(w, "_done", False)
        is_overdue = not is_done and w.date_end and w.date_end < today

        # Проверяем, попадает ли задача в выбранный период по plan_hours
        has_hours_in_period = False
        ph = w.plan_hours or {}
        for k, v in ph.items():
            try:
                y_str, m_str = k.split("-")
                y_int, m_int = int(y_str), int(m_str)
                if y_int in years_set and (not months_set or m_int in months_set):
                    if v and float(v) > 0:
                        has_hours_in_period = True
                        break
            except (ValueError, TypeError):
                pass

        # Определяем, попадает ли задача в период по датам
        in_period = False
        if months_set and len(months_set) == 1:
            m = list(months_set)[0]
            for y in years:
                from datetime import date

                sel_start = date(y, m, 1)
                sel_end = date(y, m + 1, 1) if m < 12 else date(y + 1, 1, 1)
                if w.date_start and w.date_end:
                    if w.date_start < sel_end and w.date_end >= sel_start:
                        in_period = True
                elif w.date_end and w.date_end >= sel_start:
                    in_period = True
        else:
            in_period = True  # все месяцы — все задачи в периоде

        task_item = {
            "id": w.id,
            "work_name": w.work_name or w.work_num or "",
            "project_name": (
                w.project.name
                if w.project
                else (
                    w.pp_project.up_project.name
                    if w.pp_project and w.pp_project.up_project
                    else (w.pp_project.name if w.pp_project else "")
                )
            ),
            "executor": w.executor.short_name if w.executor else "",
            "date_end": w.date_end.isoformat() if w.date_end else "",
            "deadline": (
                (w.date_end or w.deadline).isoformat()
                if (w.date_end or w.deadline)
                else ""
            ),
            "status": "done" if is_done else ("overdue" if is_overdue else "inwork"),
        }

        if is_done:
            done.append(task_item)
        elif is_overdue:
            overdue.append(task_item)
        elif in_period or has_hours_in_period:
            planned.append(task_item)
            not_done.append(task_item)

    return {
        "summary": {
            "planned_count": len(planned),
            "overdue_count": len(overdue),
            "done_count": len(done),
            "not_done_count": len(not_done),
            "planned": planned,
            "overdue": overdue,
            "done": done,
            "not_done": not_done,
        }
    }


class PlanAnalyticsView(APIView):
    """GET /api/analytics/plan/ — иерархическая аналитика с мульти-фильтрами."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        emp = getattr(request.user, "employee", None)

        # ── Параметры (все мульти-выбор) ──
        years = _int_list_param(request, "years") or [today.year]
        months_filter = _int_list_param(request, "months")
        project_ids = _int_list_param(request, "project_ids")
        product_ids = _int_list_param(request, "product_ids")
        dept_codes = _str_list_param(request, "dept_codes")
        center_ids = _int_list_param(request, "center_ids")
        sector_ids = _int_list_param(request, "sector_ids")
        executor_ids = _int_list_param(request, "executor_ids")

        all_norms = _get_calendar_norms(years)

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
                "pp_stage",
            )
        )

        # Фильтр по НТЦ-центрам
        if center_ids:
            base = base.filter(department__ntc_center_id__in=center_ids)

        # Фильтр по годам: включаем работы с датами в выбранных годах
        # и работы без дат (у них могут быть plan_hours для нужного года)
        year_q = Q(date_start__isnull=True, date_end__isnull=True)
        for y in years:
            year_q |= (
                Q(date_start__year__lte=y, date_end__year__gte=y)
                | Q(date_start__year=y)
                | Q(date_end__year=y)
                | Q(date_start__isnull=True, date_end__year__gte=y)
                | Q(date_end__isnull=True, date_start__year__lte=y)
            )
        base = base.filter(year_q)

        # Фильтр по проектам / изделиям
        if product_ids:
            base = base.filter(pp_project__up_product_id__in=product_ids)
        elif project_ids:
            base = base.filter(
                Q(project_id__in=project_ids)
                | Q(pp_project__up_project_id__in=project_ids)
            )

        # Prefetch TaskExecutor
        te_qs = TaskExecutor.objects.select_related("executor")
        base = base.prefetch_related(
            Prefetch("task_executors", queryset=te_qs, to_attr="_prefetched_executors")
        )

        works_list = list(base)

        # ── Определяем режим отображения по роли ──
        role_info = _get_role_info(emp)
        role = role_info["role"]

        # Конкретные сотрудники запрошены через чипы
        if executor_ids:
            if len(executor_ids) == 1:
                return self._respond_employee(
                    request,
                    executor_ids[0],
                    works_list,
                    all_norms,
                    years,
                    months_filter,
                    role_info,
                    emp,
                )
            return self._respond_employees_list(
                request,
                executor_ids,
                works_list,
                all_norms,
                years,
                months_filter,
                role_info,
                emp,
            )

        # user → личный план
        if role == "user":
            return self._respond_employee(
                request,
                emp.pk if emp else 0,
                works_list,
                all_norms,
                years,
                months_filter,
                role_info,
                emp,
            )

        # sector_head → по умолчанию свой сектор
        if role == "sector_head" and not dept_codes and not sector_ids:
            sid = emp.sector_id if emp and emp.sector_id else 0
            return self._respond_sector(
                request,
                sid,
                works_list,
                all_norms,
                years,
                months_filter,
                role_info,
                emp,
            )

        # dept_head/dept_deputy → по умолчанию свой отдел
        if role in ("dept_head", "dept_deputy") and not dept_codes and not sector_ids:
            dc = emp.department.code if emp and emp.department else ""
            return self._respond_dept(
                request, dc, works_list, all_norms, years, months_filter, role_info, emp
            )

        # Секторы выбраны через чипы
        if sector_ids:
            if len(sector_ids) == 1:
                return self._respond_sector(
                    request,
                    sector_ids[0],
                    works_list,
                    all_norms,
                    years,
                    months_filter,
                    role_info,
                    emp,
                )
            # Несколько секторов — фильтруем работы по секторам и показываем отдел
            filtered = [w for w in works_list if w.sector_id in set(sector_ids)]
            if dept_codes and len(dept_codes) == 1:
                return self._respond_dept(
                    request,
                    dept_codes[0],
                    filtered,
                    all_norms,
                    years,
                    months_filter,
                    role_info,
                    emp,
                )
            return self._respond_all_depts(
                request, filtered, all_norms, years, months_filter, role_info, emp
            )

        # Отделы выбраны через чипы
        if dept_codes:
            if len(dept_codes) == 1:
                return self._respond_dept(
                    request,
                    dept_codes[0],
                    works_list,
                    all_norms,
                    years,
                    months_filter,
                    role_info,
                    emp,
                )
            filtered = [
                w
                for w in works_list
                if w.department and w.department.code in set(dept_codes)
            ]
            return self._respond_all_depts(
                request,
                filtered,
                all_norms,
                years,
                months_filter,
                role_info,
                emp,
                show_sectors=True,
            )

        # Верхний уровень — все отделы
        return self._respond_all_depts(
            request, works_list, all_norms, years, months_filter, role_info, emp
        )

    # ── Ответ: конкретный сотрудник ──────────────────────────────────────

    def _respond_employee(
        self,
        request,
        executor_id,
        works,
        all_norms,
        years,
        months_filter,
        role_info,
        emp,
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

        plan = _build_employee_plan(
            executor_id, emp_works, all_norms, years, months_filter
        )
        absences = _get_absences(executor_id, years)

        return Response(
            {
                "view": "employee",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "absences": absences,
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
                **plan,
                **self._nav_context(works, role_info, emp, years),
            }
        )

    # ── Ответ: список сотрудников (мульти-выбор) ─────────────────────────

    def _respond_employees_list(
        self,
        request,
        executor_ids,
        works,
        all_norms,
        years,
        months_filter,
        role_info,
        emp,
    ):
        executor_set = set(executor_ids)
        employees = self._collect_employees_for_works(works)
        employees = {
            eid: info for eid, info in employees.items() if eid in executor_set
        }

        employees_data = []
        for e_id, e_info in sorted(employees.items(), key=lambda x: x[1]["name"]):
            plan = _build_employee_plan(
                e_id, e_info["works"], all_norms, years, months_filter
            )
            employees_data.append({"id": e_id, "name": e_info["name"], **plan})

        agg = self._aggregate_months(employees_data)

        return Response(
            {
                "view": "employees",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "employees": employees_data,
                **agg,
                **self._nav_context(works, role_info, emp, years),
            }
        )

    # ── Ответ: сектор ────────────────────────────────────────────────────

    def _respond_sector(
        self, request, sector_id, works, all_norms, years, months_filter, role_info, emp
    ):
        sector = (
            Sector.objects.filter(pk=sector_id).select_related("department").first()
        )
        sector_name = (sector.name or sector.code) if sector else "—"

        employees = self._collect_employees_for_works(works, sector_id=sector_id)
        employees_data = []
        for e_id, e_info in sorted(employees.items(), key=lambda x: x[1]["name"]):
            plan = _build_employee_plan(
                e_id, e_info["works"], all_norms, years, months_filter
            )
            employees_data.append({"id": e_id, "name": e_info["name"], **plan})

        sector_months = self._aggregate_months(employees_data)

        return Response(
            {
                "view": "sector",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "sector": {"id": sector_id, "name": sector_name},
                "employees": employees_data,
                "employee_count": len(employees_data),
                "months": sector_months["months"],
                "total_planned": sector_months["total_planned"],
                "total_norm": sector_months["total_norm"],
                "total_load_pct": sector_months["total_load_pct"],
                **self._nav_context(works, role_info, emp, years),
            }
        )

    # ── Ответ: отдел ─────────────────────────────────────────────────────

    def _respond_dept(
        self, request, dept_code, works, all_norms, years, months_filter, role_info, emp
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
            s_works = sectors_map[s_id]
            employees = self._collect_employees_for_works(
                s_works, sector_id=s_id if s_id else None
            )
            emp_plans = []
            for e_id, e_info in sorted(employees.items(), key=lambda x: x[1]["name"]):
                plan = _build_employee_plan(
                    e_id, e_info["works"], all_norms, years, months_filter
                )
                emp_plans.append({"id": e_id, "name": e_info["name"], **plan})

            agg = self._aggregate_months(emp_plans)
            sectors_data.append(
                {
                    "id": s_id,
                    "name": sector_names.get(
                        s_id, "Без сектора" if s_id == 0 else f"Сектор {s_id}"
                    ),
                    "employees": emp_plans,
                    **agg,
                }
            )

        dept_agg = self._aggregate_months(sectors_data)
        summary = _build_works_summary(dept_works, years, months_filter)
        emp_count = sum(len(s.get("employees", [])) for s in sectors_data)

        return Response(
            {
                "view": "dept",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "dept": {"code": dept_code, "name": dept_name},
                "sectors": sectors_data,
                "employee_count": emp_count,
                **dept_agg,
                **summary,
                **self._nav_context(
                    dept_works, role_info, emp, years, show_sectors=True
                ),
            }
        )

    # ── Ответ: все отделы ─────────────────────────────────────────────────

    def _respond_all_depts(
        self,
        request,
        works,
        all_norms,
        years,
        months_filter,
        role_info,
        emp,
        show_sectors=False,
    ):
        dept_map = defaultdict(list)
        for w in works:
            code = w.department.code if w.department else "—"
            dept_map[code].append(w)

        dept_names = {}
        all_sector_names = {}
        for d in Department.objects.prefetch_related("sectors").all():
            dept_names[d.code] = d.name
            for s in d.sectors.all():
                all_sector_names[s.pk] = s.name or s.code

        depts_data = []
        for code in sorted(dept_map.keys()):
            d_works = dept_map[code]

            # Группируем по секторам для drilldown-данных
            sectors_map = defaultdict(list)
            for w in d_works:
                sectors_map[w.sector_id or 0].append(w)

            sectors_data = []
            all_emp_plans = []
            for s_id in sorted(sectors_map.keys()):
                s_works = sectors_map[s_id]
                employees = self._collect_employees_for_works(
                    s_works, sector_id=s_id if s_id else None
                )
                emp_plans = []
                for e_id, e_info in sorted(
                    employees.items(), key=lambda x: x[1]["name"]
                ):
                    plan = _build_employee_plan(
                        e_id, e_info["works"], all_norms, years, months_filter
                    )
                    emp_plans.append({"id": e_id, "name": e_info["name"], **plan})
                all_emp_plans.extend(emp_plans)

                s_agg = self._aggregate_months(emp_plans)
                sectors_data.append(
                    {
                        "id": s_id,
                        "name": all_sector_names.get(
                            s_id, "Без сектора" if s_id == 0 else f"Сектор {s_id}"
                        ),
                        "employees": emp_plans,
                        **s_agg,
                    }
                )

            agg = self._aggregate_months(sectors_data)
            depts_data.append(
                {
                    "code": code,
                    "name": dept_names.get(code, code),
                    "employee_count": len(all_emp_plans),
                    "sectors": sectors_data,
                    **agg,
                }
            )

        total_agg = self._aggregate_months(depts_data)
        summary = _build_works_summary(works, years, months_filter)
        total_emp = sum(d.get("employee_count", 0) for d in depts_data)

        return Response(
            {
                "view": "all",
                "years": years,
                "months_filter": months_filter,
                "role_info": role_info,
                "depts": depts_data,
                "employee_count": total_emp,
                **total_agg,
                **summary,
                **self._nav_context(
                    works, role_info, emp, years, show_sectors=show_sectors
                ),
            }
        )

    # ── Вспомогательные ──────────────────────────────────────────────────

    def _collect_employees_for_works(self, works, sector_id=None):
        employees = {}
        seen = set()  # (employee_id, work_id) — избегаем O(n) проверки `in list`
        for w in works:
            if w.executor_id:
                e = w.executor
                if sector_id and e and e.sector_id != sector_id:
                    pass
                elif e:
                    if e.pk not in employees:
                        employees[e.pk] = {"name": e.short_name, "works": []}
                    pair = (e.pk, w.pk)
                    if pair not in seen:
                        seen.add(pair)
                        employees[e.pk]["works"].append(w)

            for te in getattr(w, "_prefetched_executors", []):
                if te.executor_id:
                    if sector_id and te.executor and te.executor.sector_id != sector_id:
                        continue
                    e = te.executor
                    if e:
                        if e.pk not in employees:
                            employees[e.pk] = {"name": e.short_name, "works": []}
                        pair = (e.pk, w.pk)
                        if pair not in seen:
                            seen.add(pair)
                            employees[e.pk]["works"].append(w)
        return employees

    def _aggregate_months(self, items):
        agg = defaultdict(lambda: {"planned": 0, "norm": 0, "filtered": True})
        for item in items:
            for m_data in item.get("months", []):
                m = m_data["month"]
                agg[m]["planned"] += m_data.get("planned", 0)
                agg[m]["norm"] += m_data.get("norm", 0)
                if m_data.get("filtered") is False:
                    agg[m]["filtered"] = False

        months = []
        total_planned = 0
        total_norm = 0
        for m in range(1, 13):
            data = agg.get(m, {"planned": 0, "norm": 0, "filtered": True})
            planned = round(data["planned"], 2)
            norm = data["norm"]
            in_filter = data["filtered"]
            load_pct = round(planned / norm * 100, 1) if norm > 0 else 0
            total_planned += planned
            if in_filter:
                total_norm += norm
            month_entry = {
                "month": m,
                "planned": planned,
                "norm": round(norm, 2),
                "load_pct": load_pct,
            }
            if not in_filter:
                month_entry["filtered"] = False
            months.append(month_entry)

        total_load = round(total_planned / total_norm * 100, 1) if total_norm > 0 else 0
        return {
            "months": months,
            "total_planned": round(total_planned, 2),
            "total_norm": round(total_norm, 2),
            "total_load_pct": total_load,
        }

    def _nav_context(self, works, role_info, emp, years, show_sectors=False):
        nav = {}
        role = role_info["role"]

        # НТЦ-центры (все, из справочника)
        if role in ("admin", "ntc_head", "ntc_deputy"):
            nav["nav_centers"] = [
                {"id": c.pk, "code": c.code, "name": c.name or c.code}
                for c in NTCCenter.objects.order_by("code")
            ]

        if role in ("admin", "ntc_head", "ntc_deputy"):
            # Отделы из работ + привязка к центру
            dept_set = {}
            for w in works:
                if w.department and w.department.code not in dept_set:
                    dept_set[w.department.code] = {
                        "code": w.department.code,
                        "center_id": w.department.ntc_center_id,
                    }
            nav["nav_depts"] = [dept_set[code] for code in sorted(dept_set.keys())]

        # Секторы показываем только если drill-down в отдел или роль dept_head/dept_deputy
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
        prod_qs = ProjectProduct.objects.only("pk", "name", "name_short", "project_id")
        if role != "admin":
            prod_qs = prod_qs.filter(project__is_hidden=False)
        nav["nav_products"] = [
            {"id": pp.pk, "name": pp.name_short or pp.name, "project_id": pp.project_id}
            for pp in prod_qs.order_by("name")
        ]

        base_year = years[0] if years else timezone.now().date().year
        nav["years"] = list(range(base_year - 3, base_year + 4))

        return nav


def _int_list_param(request, name):
    val = request.GET.get(name, "").strip()
    if not val:
        return []
    result = []
    for part in val.split(","):
        part = part.strip()
        if part:
            try:
                result.append(int(part))
            except (ValueError, TypeError):
                pass
    return result


def _str_list_param(request, name):
    val = request.GET.get(name, "").strip()
    if not val:
        return []
    return [p.strip() for p in val.split(",") if p.strip()]
