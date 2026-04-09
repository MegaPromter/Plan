"""
API Dashboard — личный план сотрудника / сводка для руководителя.

GET /api/dashboard/?year=2026&month=3
"""
import calendar as cal_mod
from collections import defaultdict
from datetime import date

from django.db.models import Exists, OuterRef, Prefetch, Q, Subquery
from django.http import JsonResponse
from django.utils import timezone
from django.views import View

from apps.api.mixins import LoginRequiredJsonMixin
from apps.api.utils import get_visibility_filter
from apps.employees.models import Employee
from apps.works.models import TaskExecutor, Work, WorkCalendar, WorkReport

from .analytics_plan import _float, _get_absences, _get_calendar_norms


# ---------------------------------------------------------------------------
#  Общий базовый queryset для dashboard (переиспользуется в обоих endpoint'ах)
# ---------------------------------------------------------------------------

_WORK_FIELDS = (
    'id', 'work_name', 'work_num', 'work_designation',
    'date_start', 'date_end', 'plan_hours',
    'executor_id', 'department_id', 'sector_id',
    'project_id', 'pp_project_id',
)
_RELATED_ONLY = (
    'department__id', 'department__code', 'department__name',
    'sector__id', 'sector__code', 'sector__name',
    'executor__id', 'executor__last_name',
    'executor__first_name', 'executor__patronymic',
    'project__id', 'project__name_short', 'project__name_full',
    'pp_project__id', 'pp_project__name',
    'pp_project__up_project_id',
    'pp_project__up_project__id',
    'pp_project__up_project__name_short',
    'pp_project__up_project__name_full',
)


def _dashboard_base_qs(user, year):
    """Базовый queryset задач за год с аннотациями для dashboard."""
    vis_q = get_visibility_filter(user)
    has_reports = Exists(WorkReport.objects.filter(work=OuterRef('pk')))
    first_report_date = Subquery(
        WorkReport.objects.filter(work=OuterRef('pk'))
        .order_by('created_at')
        .values('created_at')[:1]
    )

    base = (
        Work.objects.filter(vis_q, show_in_plan=True)
        .annotate(_done=has_reports, _report_date=first_report_date)
        .select_related('department', 'sector', 'executor',
                        'project', 'pp_project', 'pp_project__up_project')
        .only(*_WORK_FIELDS, *_RELATED_ONLY)
    )

    year_q = (
        Q(date_start__year__lte=year, date_end__year__gte=year)
        | Q(date_start__year=year)
        | Q(date_end__year=year)
        | Q(date_start__isnull=True, date_end__isnull=True)
        | Q(date_start__isnull=True, date_end__year=year)
        | Q(date_start__year=year, date_end__isnull=True)
    )
    base = base.filter(year_q)

    te_qs = TaskExecutor.objects.select_related('executor')
    base = base.prefetch_related(
        Prefetch('task_executors', queryset=te_qs, to_attr='_prefetched_executors')
    )

    return base


# ---------------------------------------------------------------------------
#  GET /api/dashboard/employee/<id>/?year=2026&month=3
# ---------------------------------------------------------------------------

class DashboardEmployeeView(LoginRequiredJsonMixin, View):
    """Задачи и долги конкретного сотрудника (ленивая загрузка по клику)."""

    def get(self, request, pk):
        today = timezone.now().date()
        year = self._int_param(request, 'year', today.year)
        month = self._int_param(request, 'month', today.month)

        emp = getattr(request.user, 'employee', None)
        if not emp or not emp.is_writer:
            return JsonResponse({'error': 'Нет доступа'}, status=403)

        norms = _get_calendar_norms([year])
        month_norm = norms.get(year, {}).get(month, 0)

        base = _dashboard_base_qs(request.user, year)
        all_works = list(base)

        month_key = f'{year}-{month:02d}'
        m_start = date(year, month, 1)
        m_end = date(year, month, cal_mod.monthrange(year, month)[1])

        tasks = []
        debts = []

        for w in all_works:
            # Проверяем, является ли pk исполнителем этой задачи
            is_executor = w.executor_id == pk
            if not is_executor:
                is_executor = any(
                    te.executor_id == pk
                    for te in getattr(w, '_prefetched_executors', [])
                )
            if not is_executor:
                continue

            # plan_hours для этого сотрудника
            ph = {}
            if w.executor_id == pk:
                ph = w.plan_hours or {}
            else:
                for te in getattr(w, '_prefetched_executors', []):
                    if te.executor_id == pk:
                        ph = te.plan_hours or {}
                        break

            is_done = getattr(w, '_done', False)
            is_overdue = not is_done and w.date_end and w.date_end < today
            status = 'done' if is_done else ('overdue' if is_overdue else 'inwork')

            hrs = float(ph.get(month_key, 0) or 0)
            in_month = hrs > 0
            if not in_month and w.date_start and w.date_end:
                in_month = w.date_end >= m_start and w.date_start <= m_end

            task_item = DashboardAPIView._serialize_task_static(
                w, ph, status, today, year)

            if status == 'overdue':
                debts.append(task_item)
            elif in_month:
                tasks.append(task_item)

        return JsonResponse({'tasks': tasks, 'debts': debts})

    @staticmethod
    def _int_param(request, name, default):
        try:
            return int(request.GET.get(name, default))
        except (ValueError, TypeError):
            return default


class DashboardAPIView(LoginRequiredJsonMixin, View):
    """GET /api/dashboard/?year=2026&month=3"""

    def get(self, request):
        today = timezone.now().date()
        year = self._int_param(request, 'year', today.year)
        month = self._int_param(request, 'month', today.month)

        emp = getattr(request.user, 'employee', None)
        if not emp:
            return JsonResponse({'error': 'Сотрудник не найден'}, status=404)

        role = emp.role

        # Доступные годы (из WorkCalendar) — distinct на уровне БД
        available_years = sorted(
            WorkCalendar.objects.values_list('year', flat=True).distinct()
        )
        if not available_years:
            available_years = [today.year]

        norms = _get_calendar_norms([year])
        month_norm = norms.get(year, {}).get(month, 0)

        base = _dashboard_base_qs(request.user, year)
        all_works = list(base)

        # ── Отсутствия ──
        absences = _get_absences(emp.pk, [year])

        result = {
            'year': year,
            'month': month,
            'available_years': available_years,
            'employee': {
                'id': emp.pk,
                'name': emp.short_name,
                'dept': emp.department.code if emp.department else '',
                'sector': (emp.sector.name or emp.sector.code) if emp.sector else '',
            },
            'role': role,
            'absences': absences,
            'team': None,
        }

        if emp.is_writer:
            # Руководитель: KPI/задачи/долги = по scope (отдел/сектор/НТЦ)
            team_data = self._build_team(emp, all_works, year, month, norms, today)
            result['team'] = team_data
            result['kpi'] = team_data['scope_kpi']
            result['tasks'] = team_data['scope_tasks']
            result['debts'] = team_data['scope_debts']
            result['done_late'] = team_data['scope_done_late']
            result['months'] = team_data['scope_months']
        else:
            # Обычный сотрудник: личные данные
            personal = self._build_personal(emp.pk, all_works, year, month, month_norm, today)
            result['kpi'] = personal['kpi']
            result['tasks'] = personal['tasks']
            result['debts'] = personal['debts']
            result['done_late'] = personal['done_late']
            result['months'] = self._build_months_overview(emp.pk, all_works, year, norms)

        response = JsonResponse(result)
        response['Cache-Control'] = 'private, max-age=10'
        return response

    # ── Личный план ──────────────────────────────────────────────────────

    def _build_personal(self, emp_id, works, year, month, month_norm, today):
        """Считает KPI, задачи, долги, done_late для сотрудника."""
        month_key = f'{year}-{month:02d}'

        my_works = [
            w for w in works
            if w.executor_id == emp_id
            or any(te.executor_id == emp_id for te in getattr(w, '_prefetched_executors', []))
        ]

        tasks = []       # задачи текущего месяца
        debts = []       # просроченные невыполненные (все)
        done_late = []   # выполненные с просрочкой
        month_planned = 0.0
        done_count = 0
        inwork_count = 0
        done_late_count = 0
        total_done = 0
        done_on_time = 0
        overdue_days_sum = 0
        overdue_days_count = 0

        for w in my_works:
            # Получаем plan_hours для этого сотрудника
            ph = {}
            if w.executor_id == emp_id:
                ph = w.plan_hours or {}
            else:
                for te in getattr(w, '_prefetched_executors', []):
                    if te.executor_id == emp_id:
                        ph = te.plan_hours or {}
                        break

            is_done = getattr(w, '_done', False)
            is_overdue = not is_done and w.date_end and w.date_end < today
            status = 'done' if is_done else ('overdue' if is_overdue else 'inwork')

            # Определяем, относится ли задача к выбранному месяцу
            hrs_this_month = _float(ph.get(month_key, 0))
            in_month = hrs_this_month > 0
            if not in_month and w.date_start and w.date_end:
                m_start = date(year, month, 1)
                m_end = date(year, month, cal_mod.monthrange(year, month)[1])
                in_month = w.date_end >= m_start and w.date_start <= m_end

            task_item = self._serialize_task(w, ph, status, today, year)

            # Долги — все просроченные невыполненные (приоритет над месяцем)
            if status == 'overdue':
                debts.append(task_item)
                if w.date_end:
                    overdue_days_sum += (today - w.date_end).days
                    overdue_days_count += 1
            elif in_month:
                month_planned += hrs_this_month
                tasks.append(task_item)
                if status == 'done':
                    done_count += 1
                else:
                    inwork_count += 1

            # Выполненные с просрочкой
            if is_done and w.date_end:
                total_done += 1
                report_date = getattr(w, '_report_date', None)
                if report_date:
                    # _report_date — datetime, сравниваем date()
                    rd = report_date.date() if hasattr(report_date, 'date') else report_date
                    if rd > w.date_end:
                        done_late.append(task_item)
                        done_late_count += 1
                    else:
                        done_on_time += 1
                else:
                    done_on_time += 1

        load_pct = round(month_planned / month_norm * 100, 1) if month_norm > 0 else 0
        # % в срок: -1 если нет выполненных (JS не покажет карточку)
        on_time_pct = round(done_on_time / total_done * 100, 1) if total_done > 0 else -1
        avg_overdue = round(overdue_days_sum / overdue_days_count, 1) if overdue_days_count > 0 else 0

        return {
            'kpi': {
                'load_pct': load_pct,
                'planned_hours': round(month_planned, 1),
                'norm_hours': round(month_norm, 1),
                'done_count': done_count,
                'overdue_count': 0,
                'inwork_count': inwork_count,
                'done_late_count': done_late_count,
                'on_time_pct': on_time_pct,
                'avg_overdue_days': avg_overdue,
                'total_debts': len(debts),
                'total_done': total_done,
            },
            'tasks': tasks,
            'debts': debts,
            'done_late': done_late,
        }

    # ── Помесячная загрузка ──────────────────────────────────────────────

    def _build_months_overview(self, emp_id, works, year, norms):
        """12 месяцев с загрузкой для чипов."""
        monthly = defaultdict(float)
        for w in works:
            if w.executor_id != emp_id:
                has_te = any(te.executor_id == emp_id for te in getattr(w, '_prefetched_executors', []))
                if not has_te:
                    continue
            ph = {}
            if w.executor_id == emp_id:
                ph = w.plan_hours or {}
            else:
                for te in getattr(w, '_prefetched_executors', []):
                    if te.executor_id == emp_id:
                        ph = te.plan_hours or {}
                        break
            for k, v in ph.items():
                try:
                    y_str, m_str = k.split('-')
                    if int(y_str) == year:
                        monthly[int(m_str)] += float(v) if v else 0
                except (ValueError, TypeError):
                    pass

        result = []
        for m in range(1, 13):
            planned = round(monthly.get(m, 0), 1)
            norm = norms.get(year, {}).get(m, 0)
            load = round(planned / norm * 100, 1) if norm > 0 else 0
            result.append({
                'month': m, 'planned': planned,
                'norm': round(norm, 1), 'load_pct': load,
            })
        return result

    # ── Сводка по команде ────────────────────────────────────────────────

    def _build_team(self, emp, works, year, month, norms, today):
        """Для начальника — сводка по подчинённым + scope KPI.

        scope = вся видимая область руководителя:
        - ntc_head/ntc_deputy/admin → весь НТЦ
        - dept_head/dept_deputy → отдел
        - sector_head → сектор
        """
        month_key = f'{year}-{month:02d}'
        month_norm = norms.get(year, {}).get(month, 0)

        # Определяем подчинённых (включая себя — для scope KPI)
        # Загружаем только поля, нужные для dashboard (short_name, dept, sector)
        _emp_only = (
            'id', 'last_name', 'first_name', 'patronymic',
            'department_id', 'sector_id',
            'department__id', 'department__code', 'department__name',
            'sector__id', 'sector__code', 'sector__name',
        )
        if emp.role in ('admin', 'ntc_head', 'ntc_deputy'):
            team_employees = Employee.objects.filter(
                is_active=True
            ).select_related('department', 'sector').only(*_emp_only)
        elif emp.role in ('dept_head', 'dept_deputy'):
            team_employees = Employee.objects.filter(
                is_active=True, department=emp.department
            ).select_related('department', 'sector').only(*_emp_only)
        elif emp.role == 'sector_head':
            team_employees = Employee.objects.filter(
                is_active=True, sector=emp.sector
            ).select_related('department', 'sector').only(*_emp_only)
        else:
            return None

        team_employees = list(team_employees)
        if not team_employees:
            return None

        team_ids = {e.pk for e in team_employees}

        # Собираем метрики и задачи для каждого сотрудника
        emp_hours = defaultdict(float)            # {eid: hours_this_month}
        emp_monthly = defaultdict(lambda: defaultdict(float))  # {eid: {month: hours}}
        emp_tasks = defaultdict(list)
        emp_debts = defaultdict(list)
        emp_done_late = defaultdict(list)

        m_start = date(year, month, 1)
        m_end = date(year, month, cal_mod.monthrange(year, month)[1])

        scope_done_count = 0
        scope_inwork_count = 0
        scope_total_done = 0
        scope_done_on_time = 0
        scope_overdue_days_sum = 0
        scope_overdue_days_count = 0
        kpi_counted_ids = set()  # дедупликация KPI по task id

        for w in works:
            executors_on_work = set()
            if w.executor_id and w.executor_id in team_ids:
                executors_on_work.add(w.executor_id)
            for te in getattr(w, '_prefetched_executors', []):
                if te.executor_id in team_ids:
                    executors_on_work.add(te.executor_id)

            if not executors_on_work:
                continue

            is_done = getattr(w, '_done', False)
            is_overdue = not is_done and w.date_end and w.date_end < today
            status = 'done' if is_done else ('overdue' if is_overdue else 'inwork')

            # KPI — считаем один раз на задачу, не на исполнителя
            any_in_month = False

            # Сериализуем задачу один раз (результат одинаков для всех исполнителей)
            task_item = None  # lazy — создаём только если нужно

            for eid in executors_on_work:
                ph = {}
                if w.executor_id == eid:
                    ph = w.plan_hours or {}
                else:
                    for te in getattr(w, '_prefetched_executors', []):
                        if te.executor_id == eid:
                            ph = te.plan_hours or {}
                            break
                hrs = float(ph.get(month_key, 0) or 0)
                emp_hours[eid] += hrs

                # Помесячная загрузка для scope months overview
                for k, v in ph.items():
                    try:
                        y_str, m_str = k.split('-')
                        if int(y_str) == year:
                            emp_monthly[eid][int(m_str)] += float(v) if v else 0
                    except (ValueError, TypeError):
                        pass

                in_month = hrs > 0
                if not in_month and w.date_start and w.date_end:
                    in_month = w.date_end >= m_start and w.date_start <= m_end
                if in_month:
                    any_in_month = True

                # Долги — все просроченные невыполненные (приоритет над месяцем)
                if status == 'overdue':
                    if task_item is None:
                        task_item = self._serialize_task(w, ph, status, today, year)
                    emp_debts[eid].append(task_item)
                elif in_month:
                    if task_item is None:
                        task_item = self._serialize_task(w, ph, status, today, year)
                    emp_tasks[eid].append(task_item)

                # Выполнено с просрочкой (per employee)
                if is_done and w.date_end:
                    report_date = getattr(w, '_report_date', None)
                    if report_date:
                        rd = report_date.date() if hasattr(report_date, 'date') else report_date
                        if rd > w.date_end:
                            if task_item is None:
                                task_item = self._serialize_task(w, ph, status, today, year)
                            emp_done_late[eid].append(task_item)

            # KPI — один раз на задачу
            if w.id not in kpi_counted_ids:
                kpi_counted_ids.add(w.id)
                if status == 'overdue':
                    if w.date_end:
                        scope_overdue_days_sum += (today - w.date_end).days
                        scope_overdue_days_count += 1
                elif any_in_month:
                    if status == 'done':
                        scope_done_count += 1
                    else:
                        scope_inwork_count += 1
                if is_done and w.date_end:
                    scope_total_done += 1
                    report_date = getattr(w, '_report_date', None)
                    if report_date:
                        rd = report_date.date() if hasattr(report_date, 'date') else report_date
                        if rd <= w.date_end:
                            scope_done_on_time += 1
                    else:
                        scope_done_on_time += 1

        # ── Scope KPI (агрегат по всем сотрудникам scope) ──
        scope_planned = round(sum(emp_hours.values()), 1)
        scope_norm = round(month_norm * len(team_ids), 1) if month_norm else 0
        scope_load = round(scope_planned / scope_norm * 100, 1) if scope_norm > 0 else 0
        scope_all_tasks = []
        scope_all_debts = []
        scope_all_done_late = []
        for eid in team_ids:
            scope_all_tasks.extend(emp_tasks.get(eid, []))
            scope_all_debts.extend(emp_debts.get(eid, []))
            scope_all_done_late.extend(emp_done_late.get(eid, []))

        on_time_pct = round(scope_done_on_time / scope_total_done * 100, 1) if scope_total_done > 0 else -1
        avg_overdue = round(scope_overdue_days_sum / scope_overdue_days_count, 1) if scope_overdue_days_count > 0 else 0

        scope_kpi = {
            'load_pct': scope_load,
            'planned_hours': scope_planned,
            'norm_hours': scope_norm,
            'done_count': scope_done_count,
            'overdue_count': 0,
            'inwork_count': scope_inwork_count,
            'done_late_count': len(scope_all_done_late),
            'on_time_pct': on_time_pct,
            'avg_overdue_days': avg_overdue,
            'total_debts': len(scope_all_debts),
            'total_done': scope_total_done,
        }

        # ── Scope months overview ──
        scope_months = []
        for m in range(1, 13):
            m_planned = round(sum(emp_monthly[eid].get(m, 0) for eid in team_ids), 1)
            m_norm_val = norms.get(year, {}).get(m, 0) * len(team_ids)
            m_load = round(m_planned / m_norm_val * 100, 1) if m_norm_val > 0 else 0
            scope_months.append({
                'month': m, 'planned': m_planned,
                'norm': round(m_norm_val, 1), 'load_pct': m_load,
            })

        # ── Группировка: отдел → сектор → сотрудники ──
        # Для dropdown исключаем самого руководителя
        display_employees = [e for e in team_employees if e.pk != emp.pk]
        dept_sectors = defaultdict(lambda: defaultdict(list))
        total_load_sum = 0
        total_overdue = 0
        total_count = 0

        for e in display_employees:
            planned = round(emp_hours.get(e.pk, 0), 1)
            load = round(planned / month_norm * 100, 1) if month_norm > 0 else 0
            tasks_list = emp_tasks.get(e.pk, [])
            debts_list = emp_debts.get(e.pk, [])
            done_count = sum(1 for t in tasks_list if t['status'] == 'done')
            inwork_count = sum(1 for t in tasks_list if t['status'] == 'inwork')
            ov = len(debts_list)
            emp_item = {
                'id': e.pk,
                'name': e.short_name,
                'planned': planned,
                'load_pct': load,
                'done_count': done_count,
                'overdue_count': ov,
                'inwork_count': inwork_count,
            }
            total_load_sum += load
            total_overdue += ov
            total_count += 1

            dept_code = e.department.code if e.department else '—'
            dept_name = e.department.name if e.department else ''
            sector_key = (e.sector.name or e.sector.code) if e.sector else ''
            dept_sectors[(dept_code, dept_name)][sector_key].append(emp_item)

        # Формируем иерархическую структуру
        DEPT_ORDER = ['021', '022', '024', '027', '028', '029', '301', '082', '084', '086']
        def _dept_sort_key(item):
            code = item[0][0]  # (dept_code, dept_name)
            try:
                return DEPT_ORDER.index(code)
            except ValueError:
                return len(DEPT_ORDER)

        departments = []
        for (dept_code, dept_name), sectors_dict in sorted(dept_sectors.items(), key=_dept_sort_key):
            dept_planned = 0
            dept_load_sum = 0
            dept_overdue = 0
            dept_done = 0
            dept_inwork = 0
            dept_count = 0

            sector_list = []
            for sector_name, emps in sorted(sectors_dict.items(), key=lambda x: x[0]):
                emps.sort(key=lambda x: (-x['overdue_count'], -x['load_pct']))
                s_planned = sum(e['planned'] for e in emps)
                s_load_sum = sum(e['load_pct'] for e in emps)
                s_overdue = sum(e['overdue_count'] for e in emps)
                s_done = sum(e['done_count'] for e in emps)
                s_inwork = sum(e['inwork_count'] for e in emps)
                s_count = len(emps)

                sector_list.append({
                    'name': sector_name or '(без сектора)',
                    'count': s_count,
                    'planned': round(s_planned, 1),
                    'avg_load_pct': round(s_load_sum / s_count, 1) if s_count else 0,
                    'overdue_count': s_overdue,
                    'done_count': s_done,
                    'inwork_count': s_inwork,
                    'employees': emps,
                })
                dept_planned += s_planned
                dept_load_sum += s_load_sum
                dept_overdue += s_overdue
                dept_done += s_done
                dept_inwork += s_inwork
                dept_count += s_count

            departments.append({
                'code': dept_code,
                'name': dept_name,
                'count': dept_count,
                'planned': round(dept_planned, 1),
                'avg_load_pct': round(dept_load_sum / dept_count, 1) if dept_count else 0,
                'overdue_count': dept_overdue,
                'done_count': dept_done,
                'inwork_count': dept_inwork,
                'sectors': sector_list,
            })

        # Порядок отделов определён DEPT_ORDER выше

        avg_load = round(total_load_sum / total_count, 1) if total_count else 0

        return {
            'total_employees': total_count,
            'avg_load_pct': avg_load,
            'total_overdue': total_overdue,
            'departments': departments,
            # Scope-level данные для KPI-карточек руководителя
            'scope_kpi': scope_kpi,
            'scope_tasks': scope_all_tasks,
            'scope_debts': scope_all_debts,
            'scope_done_late': scope_all_done_late,
            'scope_months': scope_months,
        }

    # ── Утилиты ──────────────────────────────────────────────────────────

    def _serialize_task(self, w, ph, status, today, year):
        return self._serialize_task_static(w, ph, status, today, year)

    @staticmethod
    def _serialize_task_static(w, ph, status, today, year):
        executor_name = ''
        if w.executor:
            executor_name = w.executor.short_name
        project_name = (
            w.project.name if w.project else
            (w.pp_project.up_project.name if w.pp_project and w.pp_project.up_project else
             (w.pp_project.name if w.pp_project else ''))
        )
        item = {
            'id': w.id,
            'work_name': w.work_name or w.work_num or '',
            'work_designation': w.work_designation or '',
            'project_name': project_name,
            'project_sort': project_name.lower() if project_name else '',
            'executor_name': executor_name,
            'date_start': w.date_start.isoformat() if w.date_start else '',
            'date_end': w.date_end.isoformat() if w.date_end else '',
            'status': status,
        }
        if status == 'overdue' and w.date_end:
            item['days_overdue'] = (today - w.date_end).days
        elif status == 'inwork' and w.date_end:
            item['days_left'] = (w.date_end - today).days
        if status == 'done':
            rd = getattr(w, '_report_date', None)
            if rd and w.date_end:
                rd_date = rd.date() if hasattr(rd, 'date') else rd
                if rd_date > w.date_end:
                    item['days_late'] = (rd_date - w.date_end).days
        return item

    @staticmethod
    def _int_param(request, name, default):
        try:
            return int(request.GET.get(name, default))
        except (ValueError, TypeError):
            return default
