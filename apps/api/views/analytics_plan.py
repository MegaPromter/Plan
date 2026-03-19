"""
API аналитики «Личный план» — иерархическая загрузка по ролям.

GET /api/analytics/plan/?year=2026
    &month=3           (опционально — фильтр по месяцу)
    &project_id=5      (опционально — фильтр по УП-проекту)
    &dept=110          (опционально — фильтр по отделу, для ntc_head)
    &sector_id=7       (опционально — фильтр по сектору, для dept_head)
    &executor_id=12    (опционально — конкретный сотрудник)
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Q, Exists, OuterRef, Sum, Prefetch
from django.http import JsonResponse
from django.utils import timezone
from django.views import View

from apps.api.mixins import LoginRequiredJsonMixin
from apps.api.utils import get_visibility_filter
from apps.employees.models import Employee, Department, Sector
from apps.works.models import Work, WorkCalendar, WorkReport, TaskExecutor


def _float(v):
    """Безопасное приведение к float."""
    if v is None:
        return 0.0
    return round(float(v), 2)


def _get_calendar_norms(year):
    """Возвращает {month_int: hours_norm} для данного года."""
    norms = {}
    for wc in WorkCalendar.objects.filter(year=year):
        norms[wc.month] = float(wc.hours_norm)
    return norms


def _get_role_info(emp):
    """Возвращает dict с информацией о роли для фронтенда."""
    if not emp:
        return {'role': 'user', 'dept': '', 'sector': '', 'sector_id': 0, 'dept_id': 0}
    return {
        'role': emp.role,
        'dept': emp.department.code if emp.department else '',
        'dept_id': emp.department_id or 0,
        'sector': (emp.sector.name or emp.sector.code) if emp.sector else '',
        'sector_id': emp.sector_id or 0,
    }


def _build_employee_plan(emp_id, works, calendar_norms, year, month_filter=None):
    """
    Считает план для одного сотрудника.
    works — список Work-объектов, где executor_id = emp_id ИЛИ есть TaskExecutor.
    Возвращает dict с задачами и помесячной загрузкой.
    """
    tasks = []
    # {month_int: total_hours}
    monthly_hours = defaultdict(float)

    for w in works:
        # plan_hours данного сотрудника по этой работе
        ph = {}

        if w.executor_id == emp_id:
            # Основной исполнитель — берём plan_hours работы
            ph = w.plan_hours or {}
        else:
            # Дополнительный исполнитель — ищем в TaskExecutor
            for te in getattr(w, '_prefetched_executors', []):
                if te.executor_id == emp_id:
                    ph = te.plan_hours or {}
                    break

        if not ph and w.executor_id != emp_id:
            continue

        # Если фильтр по месяцу — проверяем что есть часы в этом месяце
        month_key = f'{year}-{month_filter:02d}' if month_filter else None
        if month_key and month_key not in ph and not ph:
            continue

        # Суммируем часы по месяцам
        for k, v in ph.items():
            try:
                y_str, m_str = k.split('-')
                if int(y_str) == year:
                    m_int = int(m_str)
                    hours_val = float(v) if v else 0
                    monthly_hours[m_int] += hours_val
            except (ValueError, TypeError):
                pass

        is_done = getattr(w, '_done', False)
        today = timezone.now().date()
        is_overdue = not is_done and w.date_end and w.date_end < today

        tasks.append({
            'id': w.id,
            'work_name': w.work_name or w.work_num or '',
            'work_num': w.work_num or '',
            'project': w.row_code or '',
            'project_name': w.project.name if w.project else '',
            'date_start': w.date_start.isoformat() if w.date_start else '',
            'date_end': w.date_end.isoformat() if w.date_end else '',
            'labor': _float(w.labor),
            'plan_hours': {k: _float(v) for k, v in ph.items()},
            'status': 'done' if is_done else ('overdue' if is_overdue else 'inwork'),
        })

    # Формируем массив по месяцам
    months_data = []
    total_planned = 0.0
    total_norm = 0.0
    for m in range(1, 13):
        planned = round(monthly_hours.get(m, 0), 2)
        norm = calendar_norms.get(m, 0)
        load_pct = round(planned / norm * 100, 1) if norm > 0 else 0
        total_planned += planned
        total_norm += norm
        months_data.append({
            'month': m,
            'key': f'{year}-{m:02d}',
            'planned': planned,
            'norm': norm,
            'load_pct': load_pct,
        })

    total_load = round(total_planned / total_norm * 100, 1) if total_norm > 0 else 0

    return {
        'tasks': tasks,
        'months': months_data,
        'total_planned': round(total_planned, 2),
        'total_norm': round(total_norm, 2),
        'total_load_pct': total_load,
    }


class PlanAnalyticsView(LoginRequiredJsonMixin, View):
    """GET /api/analytics/plan/ — иерархическая аналитика личного плана."""

    def get(self, request):
        today = timezone.now().date()
        emp = getattr(request.user, 'employee', None)

        # ── Параметры ──
        year = _int_param(request, 'year', today.year)
        month = _int_param(request, 'month', 0)  # 0 = все месяцы
        project_id = _int_param(request, 'project_id', 0)
        dept_code = request.GET.get('dept', '')
        sector_id = _int_param(request, 'sector_id', 0)
        executor_id = _int_param(request, 'executor_id', 0)

        # Календарные нормы
        calendar_norms = _get_calendar_norms(year)

        # ── Базовый queryset ──
        vis_q = get_visibility_filter(request.user)
        has_reports = Exists(WorkReport.objects.filter(work=OuterRef('pk')))

        base = (
            Work.objects.filter(vis_q, show_in_plan=True)
            .annotate(_done=has_reports)
            .select_related('department', 'sector', 'executor', 'project')
        )

        # Фильтр по году: задачи, активные в году ИЛИ имеющие plan_hours в этом году
        year_q = (
            Q(date_start__year__lte=year, date_end__year__gte=year)
            | Q(date_start__year=year)
            | Q(date_end__year=year)
        )
        base = base.filter(year_q)

        # Фильтр по проекту
        if project_id:
            base = base.filter(project_id=project_id)

        # Prefetch TaskExecutor для всех работ
        te_qs = TaskExecutor.objects.select_related('executor')
        base = base.prefetch_related(
            Prefetch('task_executors', queryset=te_qs, to_attr='_prefetched_executors')
        )

        works_list = list(base)

        # ── Определяем режим отображения по роли ──
        role_info = _get_role_info(emp)
        role = role_info['role']

        # Конкретный сотрудник запрошен
        if executor_id:
            return self._respond_employee(
                request, executor_id, works_list, calendar_norms, year, month,
                role_info, emp
            )

        # Если обычный user или sector_head без drill-down → личный план
        if role in ('user', 'sector_head') and not dept_code and not sector_id:
            if role == 'user':
                # Обычный исполнитель — только свой план
                return self._respond_employee(
                    request, emp.pk if emp else 0, works_list, calendar_norms,
                    year, month, role_info, emp
                )
            # sector_head — план сектора
            return self._respond_sector(
                request, emp.sector_id if emp and emp.sector_id else 0,
                works_list, calendar_norms, year, month, role_info, emp
            )

        # dept_head/dept_deputy
        if role in ('dept_head', 'dept_deputy'):
            if sector_id:
                return self._respond_sector(
                    request, sector_id, works_list, calendar_norms,
                    year, month, role_info, emp
                )
            return self._respond_dept(
                request, emp.department.code if emp and emp.department else '',
                works_list, calendar_norms, year, month, role_info, emp
            )

        # ntc_head/ntc_deputy/admin
        if dept_code:
            if sector_id:
                return self._respond_sector(
                    request, sector_id, works_list, calendar_norms,
                    year, month, role_info, emp
                )
            return self._respond_dept(
                request, dept_code, works_list, calendar_norms,
                year, month, role_info, emp
            )

        # Верхний уровень — все отделы
        return self._respond_all_depts(
            request, works_list, calendar_norms, year, month, role_info, emp
        )

    # ── Ответ: конкретный сотрудник ──────────────────────────────────────

    def _respond_employee(self, request, executor_id, works, cal_norms, year, month, role_info, emp):
        target = Employee.objects.filter(pk=executor_id).select_related('department', 'sector').first()
        if not target:
            return JsonResponse({'error': 'Сотрудник не найден'}, status=404)

        # Фильтруем работы: основной исполнитель ИЛИ доп.исполнитель
        emp_works = []
        for w in works:
            if w.executor_id == executor_id:
                emp_works.append(w)
            elif any(te.executor_id == executor_id for te in getattr(w, '_prefetched_executors', [])):
                emp_works.append(w)

        plan = _build_employee_plan(executor_id, emp_works, cal_norms, year, month or None)

        return JsonResponse({
            'view': 'employee',
            'year': year,
            'month': month,
            'role_info': role_info,
            'employee': {
                'id': target.pk,
                'name': target.short_name,
                'dept': target.department.code if target.department else '',
                'sector': (target.sector.name or target.sector.code) if target.sector else '',
            },
            **plan,
            **self._nav_context(works, role_info, emp, year),
        })

    # ── Ответ: сектор ────────────────────────────────────────────────────

    def _respond_sector(self, request, sector_id, works, cal_norms, year, month, role_info, emp):
        sector = Sector.objects.filter(pk=sector_id).select_related('department').first()
        sector_name = (sector.name or sector.code) if sector else '—'

        # Собираем сотрудников сектора
        employees = self._collect_employees_for_works(works, sector_id=sector_id)

        employees_data = []
        for e_id, e_info in sorted(employees.items(), key=lambda x: x[1]['name']):
            plan = _build_employee_plan(e_id, e_info['works'], cal_norms, year, month or None)
            employees_data.append({
                'id': e_id,
                'name': e_info['name'],
                **plan,
            })

        # Агрегация по сектору
        sector_months = self._aggregate_months(employees_data)

        return JsonResponse({
            'view': 'sector',
            'year': year,
            'month': month,
            'role_info': role_info,
            'sector': {'id': sector_id, 'name': sector_name},
            'employees': employees_data,
            'months': sector_months['months'],
            'total_planned': sector_months['total_planned'],
            'total_norm': sector_months['total_norm'],
            'total_load_pct': sector_months['total_load_pct'],
            **self._nav_context(works, role_info, emp, year),
        })

    # ── Ответ: отдел ─────────────────────────────────────────────────────

    def _respond_dept(self, request, dept_code, works, cal_norms, year, month, role_info, emp):
        dept = Department.objects.filter(code=dept_code).first()
        dept_name = dept.name if dept else dept_code

        # Работы этого отдела
        dept_works = [w for w in works if w.department and w.department.code == dept_code]

        # Группируем по секторам
        sectors_map = defaultdict(list)
        for w in dept_works:
            s_id = w.sector_id or 0
            sectors_map[s_id].append(w)

        # Получаем названия секторов
        sector_names = {}
        if dept:
            for s in dept.sectors.all():
                sector_names[s.pk] = s.name or s.code

        sectors_data = []
        for s_id in sorted(sectors_map.keys()):
            s_works = sectors_map[s_id]
            employees = self._collect_employees_for_works(s_works)
            emp_plans = []
            for e_id, e_info in sorted(employees.items(), key=lambda x: x[1]['name']):
                plan = _build_employee_plan(e_id, e_info['works'], cal_norms, year, month or None)
                emp_plans.append({'id': e_id, 'name': e_info['name'], **plan})

            agg = self._aggregate_months(emp_plans)
            sectors_data.append({
                'id': s_id,
                'name': sector_names.get(s_id, 'Без сектора' if s_id == 0 else f'Сектор {s_id}'),
                'employees': emp_plans,
                **agg,
            })

        # Агрегация по отделу
        dept_agg = self._aggregate_months(sectors_data)

        return JsonResponse({
            'view': 'dept',
            'year': year,
            'month': month,
            'role_info': role_info,
            'dept': {'code': dept_code, 'name': dept_name},
            'sectors': sectors_data,
            **dept_agg,
            **self._nav_context(dept_works, role_info, emp, year),
        })

    # ── Ответ: все отделы (NTC/admin) ────────────────────────────────────

    def _respond_all_depts(self, request, works, cal_norms, year, month, role_info, emp):
        # Группируем работы по отделам
        dept_map = defaultdict(list)
        for w in works:
            code = w.department.code if w.department else '—'
            dept_map[code].append(w)

        # Получаем названия отделов
        dept_names = {}
        for d in Department.objects.all():
            dept_names[d.code] = d.name

        depts_data = []
        for code in sorted(dept_map.keys()):
            d_works = dept_map[code]
            employees = self._collect_employees_for_works(d_works)
            emp_plans = []
            for e_id, e_info in sorted(employees.items(), key=lambda x: x[1]['name']):
                plan = _build_employee_plan(e_id, e_info['works'], cal_norms, year, month or None)
                emp_plans.append({'id': e_id, 'name': e_info['name'], **plan})

            agg = self._aggregate_months(emp_plans)
            depts_data.append({
                'code': code,
                'name': dept_names.get(code, code),
                'employee_count': len(emp_plans),
                **agg,
            })

        total_agg = self._aggregate_months(depts_data)

        return JsonResponse({
            'view': 'all',
            'year': year,
            'month': month,
            'role_info': role_info,
            'depts': depts_data,
            **total_agg,
            **self._nav_context(works, role_info, emp, year),
        })

    # ── Вспомогательные ──────────────────────────────────────────────────

    def _collect_employees_for_works(self, works, sector_id=None):
        """
        Собирает dict {emp_id: {name, works: [...]}} для списка работ.
        Если sector_id задан — фильтрует только сотрудников этого сектора.
        """
        employees = {}  # {emp_id: {'name': str, 'works': [Work]}}
        for w in works:
            # Основной исполнитель
            if w.executor_id:
                e = w.executor
                if sector_id and e and e.sector_id != sector_id:
                    pass
                elif e:
                    if e.pk not in employees:
                        employees[e.pk] = {'name': e.short_name, 'works': []}
                    employees[e.pk]['works'].append(w)

            # Дополнительные исполнители
            for te in getattr(w, '_prefetched_executors', []):
                if te.executor_id:
                    if sector_id and te.executor and te.executor.sector_id != sector_id:
                        continue
                    e = te.executor
                    if e:
                        if e.pk not in employees:
                            employees[e.pk] = {'name': e.short_name, 'works': []}
                        if w not in employees[e.pk]['works']:
                            employees[e.pk]['works'].append(w)
        return employees

    def _aggregate_months(self, items):
        """
        Агрегирует months из списка items (каждый имеет 'months' массив).
        Возвращает dict с months, total_planned, total_norm, total_load_pct.
        Норма суммируется по всем элементам (каждый сотрудник имеет свою норму).
        """
        agg = defaultdict(lambda: {'planned': 0, 'norm': 0})
        for item in items:
            for m_data in item.get('months', []):
                m = m_data['month']
                agg[m]['planned'] += m_data.get('planned', 0)
                agg[m]['norm'] += m_data.get('norm', 0)

        months = []
        total_planned = 0
        total_norm = 0
        for m in range(1, 13):
            data = agg.get(m, {'planned': 0, 'norm': 0})
            planned = round(data['planned'], 2)
            norm = data['norm']
            load_pct = round(planned / norm * 100, 1) if norm > 0 else 0
            total_planned += planned
            total_norm += norm
            months.append({
                'month': m,
                'key': f'?-{m:02d}',  # год неизвестен на уровне агрегации
                'planned': planned,
                'norm': norm,
                'load_pct': load_pct,
            })

        total_load = round(total_planned / total_norm * 100, 1) if total_norm > 0 else 0
        return {
            'months': months,
            'total_planned': round(total_planned, 2),
            'total_norm': round(total_norm, 2),
            'total_load_pct': total_load,
        }

    def _nav_context(self, works, role_info, emp, year):
        """Контекст навигации: доступные отделы, секторы, проекты."""
        nav = {}
        role = role_info['role']

        # Доступные отделы (для ntc_head/admin)
        if role in ('admin', 'ntc_head', 'ntc_deputy'):
            dept_codes = sorted(set(
                w.department.code for w in works if w.department
            ))
            nav['nav_depts'] = dept_codes

        # Доступные секторы (для dept_head)
        if role in ('admin', 'ntc_head', 'ntc_deputy', 'dept_head', 'dept_deputy'):
            sectors_set = {}
            for w in works:
                if w.sector_id and w.sector:
                    sectors_set[w.sector_id] = w.sector.name or w.sector.code
            nav['nav_sectors'] = [
                {'id': sid, 'name': sname}
                for sid, sname in sorted(sectors_set.items(), key=lambda x: x[1])
            ]

        # Доступные проекты
        projects_set = {}
        for w in works:
            if w.project_id and w.project:
                projects_set[w.project_id] = w.project.name
        nav['nav_projects'] = [
            {'id': pid, 'name': pname}
            for pid, pname in sorted(projects_set.items(), key=lambda x: x[1])
        ]

        # Годы для переключения
        nav['years'] = list(range(year - 3, year + 4))

        return nav


def _int_param(request, name, default):
    """Безопасно извлекает int-параметр из GET."""
    val = request.GET.get(name, '')
    try:
        return int(val) if val else default
    except (ValueError, TypeError):
        return default
