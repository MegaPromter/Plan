"""
API аналитики: загрузка по отделам, выполнение по месяцам, просроченные, дедлайны.
"""
from decimal import Decimal

from django.db.models import Count, Q, Exists, OuterRef, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views import View

from apps.api.mixins import LoginRequiredJsonMixin
from apps.api.utils import get_visibility_filter
from apps.employees.models import Employee
from apps.works.models import PPProject, Work, WorkCalendar, WorkReport


class WorkloadAnalyticsView(LoginRequiredJsonMixin, View):
    """GET /api/analytics/workload/?year=2026"""

    def get(self, request):
        today = timezone.now().date()
        year = request.GET.get('year', today.year)
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = today.year

        base = Work.objects.filter(
            get_visibility_filter(request.user),
            show_in_plan=True,
        )

        # Аннотируем: есть ли отчёты (done)
        has_reports = Exists(WorkReport.objects.filter(work=OuterRef('pk')))
        base = base.annotate(_done=has_reports)

        # Фильтр по году: задачи активные в данном году
        year_q = (
            Q(date_start__year__lte=year, date_end__year__gte=year)
            | Q(date_start__year=year)
            | Q(date_end__year=year)
        )
        qs = base.filter(year_q)

        # 1. По отделам
        by_dept = []
        dept_data = (
            qs.values('department__code')
            .annotate(
                total=Count('id'),
                done=Count('id', filter=Q(_done=True)),
                overdue=Count('id', filter=Q(
                    _done=False,
                    date_end__lt=today,
                )),
            )
            .order_by('department__code')
        )
        for row in dept_data:
            code = row['department__code'] or '—'
            by_dept.append({
                'dept': code,
                'total': row['total'],
                'done': row['done'],
                'overdue': row['overdue'],
            })

        # 2. По месяцам (текущий год)
        monthly = []
        for m in range(1, 13):
            month_q = Q(date_end__year=year, date_end__month=m)
            agg = qs.filter(month_q).aggregate(
                total=Count('id'),
                done=Count('id', filter=Q(_done=True)),
            )
            monthly.append({
                'month': f'{year}-{m:02d}',
                'total': agg['total'],
                'done': agg['done'],
            })

        # 3. Просроченные (топ-10)
        overdue_qs = (
            qs.filter(_done=False, date_end__lt=today)
            .select_related('department', 'executor')
            .order_by('date_end')[:10]
        )
        top_overdue = []
        for w in overdue_qs:
            top_overdue.append({
                'id': w.id,
                'work_name': w.work_name or '',
                'dept': (w.department.code if w.department else ''),
                'executor': (w.executor.short_name if w.executor else ''),
                'deadline': w.date_end.isoformat() if w.date_end else '',
                'days_overdue': (today - w.date_end).days if w.date_end else 0,
            })

        # 4. Ближайшие дедлайны (10)
        upcoming_qs = (
            qs.filter(_done=False, date_end__gte=today)
            .select_related('department', 'executor')
            .order_by('date_end')[:10]
        )
        upcoming = []
        for w in upcoming_qs:
            upcoming.append({
                'id': w.id,
                'work_name': w.work_name or '',
                'dept': (w.department.code if w.department else ''),
                'executor': (w.executor.short_name if w.executor else ''),
                'deadline': w.date_end.isoformat() if w.date_end else '',
                'days_left': (w.date_end - today).days if w.date_end else 0,
            })

        response = JsonResponse({
            'year': year,
            'by_dept': by_dept,
            'monthly': monthly,
            'top_overdue': top_overdue,
            'upcoming': upcoming,
        })
        response['Cache-Control'] = 'private, max-age=15'
        return response


class EmployeeAnalyticsView(LoginRequiredJsonMixin, View):
    """GET /api/analytics/employee/?year=2026&executor_id=N"""

    def get(self, request):
        today = timezone.now().date()
        year = request.GET.get('year', today.year)
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = today.year

        emp = getattr(request.user, 'employee', None)

        # Определяем целевого сотрудника
        executor_id = request.GET.get('executor_id')
        if executor_id:
            try:
                executor_id = int(executor_id)
            except (ValueError, TypeError):
                executor_id = None

        # Права: is_writer может смотреть любого (в пределах visibility), user — только себя
        if emp and emp.is_writer and executor_id:
            # Проверяем что целевой сотрудник виден текущему пользователю
            vis_q = get_visibility_filter(request.user)
            visible_depts = set(
                Work.objects.filter(vis_q).values_list('department_id', flat=True).distinct()
            )
            target_emp = Employee.objects.filter(pk=executor_id).select_related('department').first()
            if target_emp and target_emp.department_id and target_emp.department_id not in visible_depts:
                target_emp = emp  # Нет доступа — показываем данные текущего пользователя
                executor_id = target_emp.pk if target_emp else None
        else:
            target_emp = emp
            if target_emp:
                executor_id = target_emp.pk

        if not target_emp:
            return JsonResponse({'error': 'Сотрудник не найден'}, status=404)

        # Базовый queryset задач сотрудника (с учётом visibility)
        vis_q = get_visibility_filter(request.user)
        has_reports = Exists(WorkReport.objects.filter(work=OuterRef('pk')))
        base = (
            Work.objects.filter(show_in_plan=True, executor=target_emp)
            .filter(vis_q)
            .annotate(_done=has_reports)
        )

        # Фильтр по году
        year_q = (
            Q(date_start__year__lte=year, date_end__year__gte=year)
            | Q(date_start__year=year)
            | Q(date_end__year=year)
        )
        qs = base.filter(year_q)

        # Сводка (один запрос вместо трёх)
        agg = qs.aggregate(
            total=Count('id'),
            done=Count('id', filter=Q(_done=True)),
            overdue=Count('id', filter=Q(_done=False, date_end__lt=today)),
        )
        total = agg['total']
        done = agg['done']
        overdue = agg['overdue']
        inwork = total - done - overdue

        # Задачи
        tasks_list = []
        for w in qs.select_related('department', 'project', 'pp_project', 'pp_project__up_project').order_by('date_end'):
            is_done = w._done
            is_overdue = not is_done and w.date_end and w.date_end < today
            if is_done:
                status = 'done'
            elif is_overdue:
                status = 'overdue'
            else:
                status = 'inwork'

            item = {
                'id': w.id,
                'work_name': w.work_name or w.work_number or '',
                'status': status,
                'deadline': w.date_end.isoformat() if w.date_end else '',
                'labor': float(w.labor) if w.labor else 0,
                'project': w.row_code or '',
                'project_name': (
                    w.project.name if w.project else
                    (w.pp_project.up_project.name if w.pp_project and w.pp_project.up_project else
                     (w.pp_project.name if w.pp_project else ''))
                ),
            }
            if status == 'overdue' and w.date_end:
                item['days_overdue'] = (today - w.date_end).days
            elif status == 'inwork' and w.date_end:
                item['days_left'] = (w.date_end - today).days
            tasks_list.append(item)

        # Помесячная загрузка (часы)
        monthly_hours = []
        cal_norms = {}
        for wc in WorkCalendar.objects.filter(year=year):
            cal_norms[wc.month] = float(wc.hours_norm)

        for m in range(1, 13):
            month_q = Q(date_end__year=year, date_end__month=m)
            agg = qs.filter(month_q).aggregate(planned=Sum('labor'))
            planned = float(agg['planned'] or 0)
            monthly_hours.append({
                'month': f'{year}-{m:02d}',
                'planned': round(planned, 1),
                'norm': cal_norms.get(m, 0),
            })

        # Список сотрудников для дропдауна (для руководителей)
        executors_list = []
        if emp and emp.is_writer:
            vis = get_visibility_filter(request.user)
            exec_ids = (
                Work.objects.filter(vis, show_in_plan=True)
                .exclude(executor__isnull=True)
                .values_list('executor_id', flat=True)
                .distinct()
            )
            for e in Employee.objects.filter(pk__in=exec_ids).select_related('department').order_by('last_name', 'first_name'):
                executors_list.append({
                    'id': e.pk,
                    'name': e.short_name,
                    'dept': e.department.code if e.department else '',
                })

        response = JsonResponse({
            'year': year,
            'executor': {
                'id': target_emp.pk,
                'name': target_emp.short_name,
                'dept': target_emp.department.code if target_emp.department else '',
            },
            'summary': {
                'total': total,
                'done': done,
                'overdue': overdue,
                'inwork': inwork,
            },
            'tasks': tasks_list,
            'monthly_hours': monthly_hours,
            'executors_list': executors_list,
        })
        response['Cache-Control'] = 'private, max-age=15'
        return response


class PPAnalyticsView(LoginRequiredJsonMixin, View):
    """GET /api/analytics/pp/?year=2026&pp_project_id=N"""

    def get(self, request):
        today = timezone.now().date()
        year = request.GET.get('year', today.year)
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = today.year

        pp_project_id = request.GET.get('pp_project_id')
        if pp_project_id:
            try:
                pp_project_id = int(pp_project_id)
            except (ValueError, TypeError):
                pp_project_id = None

        has_reports = Exists(WorkReport.objects.filter(work=OuterRef('pk')))
        base = Work.objects.filter(show_in_pp=True).annotate(_done=has_reports)

        # Фильтр по году
        year_q = (
            Q(date_start__year__lte=year, date_end__year__gte=year)
            | Q(date_start__year=year)
            | Q(date_end__year=year)
        )
        qs = base.filter(year_q)

        # Фильтр по ПП-проекту
        if pp_project_id:
            qs = qs.filter(pp_project_id=pp_project_id)

        # 1. Сводка
        agg = qs.aggregate(
            total_tasks=Count('id'),
            total_labor=Sum('labor'),
            total_sheets=Sum('sheets_a4'),
            done=Count('id', filter=Q(_done=True)),
            overdue=Count('id', filter=Q(_done=False, date_end__lt=today)),
        )
        summary = {
            'total_tasks': agg['total_tasks'] or 0,
            'total_labor': round(float(agg['total_labor'] or 0), 1),
            'total_sheets': round(float(agg['total_sheets'] or 0), 1),
            'done': agg['done'] or 0,
            'overdue': agg['overdue'] or 0,
        }

        # 2. По проектам
        by_project = []
        proj_data = (
            qs.values('pp_project_id', 'pp_project__name')
            .annotate(
                tasks=Count('id'),
                labor=Sum('labor'),
                sheets=Sum('sheets_a4'),
                done=Count('id', filter=Q(_done=True)),
                overdue=Count('id', filter=Q(_done=False, date_end__lt=today)),
            )
            .order_by('-labor')
        )
        for row in proj_data:
            if not row['pp_project_id']:
                continue
            by_project.append({
                'id': row['pp_project_id'],
                'name': row['pp_project__name'] or '—',
                'tasks': row['tasks'],
                'labor': round(float(row['labor'] or 0), 1),
                'sheets': round(float(row['sheets'] or 0), 1),
                'done': row['done'],
                'overdue': row['overdue'],
            })

        # 3. По отделам
        by_dept = []
        dept_data = (
            qs.values('department__code')
            .annotate(
                tasks=Count('id'),
                labor=Sum('labor'),
                sheets=Sum('sheets_a4'),
            )
            .order_by('department__code')
        )
        for row in dept_data:
            by_dept.append({
                'dept': row['department__code'] or '—',
                'tasks': row['tasks'],
                'labor': round(float(row['labor'] or 0), 1),
                'sheets': round(float(row['sheets'] or 0), 1),
            })

        # 4. По типам работ
        by_type = []
        type_data = (
            qs.exclude(task_type='')
            .values('task_type')
            .annotate(count=Count('id'), labor=Sum('labor'))
            .order_by('-count')
        )
        for row in type_data:
            by_type.append({
                'task_type': row['task_type'] or '—',
                'count': row['count'],
                'labor': round(float(row['labor'] or 0), 1),
            })

        # 5. Помесячно
        monthly = []
        for m in range(1, 13):
            month_q = Q(date_end__year=year, date_end__month=m)
            m_agg = qs.filter(month_q).aggregate(
                total=Count('id'),
                labor=Sum('labor'),
                done=Count('id', filter=Q(_done=True)),
            )
            monthly.append({
                'month': f'{year}-{m:02d}',
                'total': m_agg['total'] or 0,
                'labor': round(float(m_agg['labor'] or 0), 1),
                'done': m_agg['done'] or 0,
            })

        # 6. Список ПП-проектов для дропдауна
        pp_projects = []
        for pp in PPProject.objects.all().order_by('name'):
            pp_projects.append({'id': pp.pk, 'name': pp.name or f'ПП #{pp.pk}'})

        response = JsonResponse({
            'year': year,
            'summary': summary,
            'by_project': by_project,
            'by_dept': by_dept,
            'by_type': by_type,
            'monthly': monthly,
            'pp_projects': pp_projects,
        })
        response['Cache-Control'] = 'private, max-age=15'
        return response
