"""
API загрузки и мощности отделов.

GET /api/enterprise/capacity/ — загрузка по НТЦ-центрам и отделам
    ?project_id=N — фильтр по проекту
    ?year=2026    — год (по умолчанию текущий)
    ?mode=staff|actual — режим расчёта мощности (штатная / фактическая)

GET /api/enterprise/capacity/dept/<dept_id>/ — помесячная детализация отдела
    ?year=2026&mode=staff|actual&project_id=N
"""
import logging
from collections import OrderedDict
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import LoginRequiredJsonMixin
from apps.employees.models import Department, Employee, NTCCenter
from apps.works.models import Work, WorkCalendar

logger = logging.getLogger(__name__)


def _level(pct):
    """Порог загрузки: <60 серый, 60-80 зелёный, 80-100 жёлтый, >100 красный."""
    if pct < 60:
        return 'low'
    elif pct < 80:
        return 'normal'
    elif pct <= 100:
        return 'high'
    return 'overload'


def _dept_capacity(dept, year, mode, cal_norms, project_id=None):
    """Считает мощность и потребность отдела за год + помесячно."""
    if mode == 'staff':
        headcount = dept.staff_count or 0
    else:
        headcount = Employee.objects.filter(
            department=dept, is_active=True,
        ).count()

    # Годовые итоги
    year_capacity = sum(cal_norms.get(m, 0) * headcount for m in range(1, 13))

    work_filter = Q(executor__department=dept, date_end__year=year)
    if project_id:
        work_filter &= (
            Q(pp_project__up_project_id=project_id)
            | Q(project_id=project_id)
        )

    year_demand = float(
        Work.objects.filter(work_filter).aggregate(total=Sum('labor'))['total']
        or Decimal('0')
    )

    loading_pct = (year_demand / year_capacity * 100) if year_capacity > 0 else 0

    # Помесячно
    monthly = []
    for m in range(1, 13):
        month_cap = cal_norms.get(m, 0) * headcount
        month_filter = work_filter & Q(date_end__month=m)
        month_demand = float(
            Work.objects.filter(month_filter).aggregate(total=Sum('labor'))['total']
            or Decimal('0')
        )
        month_pct = (month_demand / month_cap * 100) if month_cap > 0 else 0
        monthly.append({
            'month': m,
            'capacity': round(month_cap, 2),
            'demand': round(month_demand, 2),
            'loading_pct': round(month_pct, 1),
            'balance': round(month_cap - month_demand, 2),
            'level': _level(month_pct),
        })

    return {
        'department_id': dept.id,
        'department_name': dept.name or dept.code,
        'department_code': dept.code,
        'headcount': headcount,
        'capacity_hours': round(year_capacity, 2),
        'demand_hours': round(year_demand, 2),
        'loading_pct': round(loading_pct, 1),
        'level': _level(loading_pct),
        'monthly': monthly,
    }


class CapacityView(LoginRequiredJsonMixin, View):
    """GET /api/enterprise/capacity/ — расчёт загрузки по НТЦ-центрам и отделам."""

    def get(self, request):
        try:
            year = int(request.GET.get('year', date.today().year))
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Невалидный год'}, status=400)
        project_id = request.GET.get('project_id')
        mode = request.GET.get('mode', 'actual')
        if mode not in ('staff', 'actual'):
            mode = 'actual'

        # Нормы по месяцам из производственного календаря
        cal_norms = {}
        for wc in WorkCalendar.objects.filter(year=year):
            cal_norms[wc.month] = float(wc.hours_norm)

        departments = Department.objects.select_related('ntc_center').order_by(
            'ntc_center__code', 'code',
        )

        # Группируем по НТЦ-центру
        centers = OrderedDict()
        no_center_depts = []

        for dept in departments:
            dept_data = _dept_capacity(dept, year, mode, cal_norms, project_id)

            if dept.ntc_center_id:
                cid = dept.ntc_center_id
                if cid not in centers:
                    c = dept.ntc_center
                    centers[cid] = {
                        'center_id': c.id,
                        'center_name': c.name or c.code,
                        'center_code': c.code,
                        'departments': [],
                        'headcount': 0,
                        'capacity_hours': 0.0,
                        'demand_hours': 0.0,
                    }
                centers[cid]['departments'].append(dept_data)
                centers[cid]['headcount'] += dept_data['headcount']
                centers[cid]['capacity_hours'] += dept_data['capacity_hours']
                centers[cid]['demand_hours'] += dept_data['demand_hours']
            else:
                no_center_depts.append(dept_data)

        # Финализируем агрегаты центров
        result_centers = []
        for cdata in centers.values():
            cap = cdata['capacity_hours']
            dem = cdata['demand_hours']
            pct = (dem / cap * 100) if cap > 0 else 0
            cdata['capacity_hours'] = round(cap, 2)
            cdata['demand_hours'] = round(dem, 2)
            cdata['loading_pct'] = round(pct, 1)
            cdata['level'] = _level(pct)
            result_centers.append(cdata)

        return JsonResponse({
            'year': year,
            'mode': mode,
            'centers': result_centers,
            'no_center_departments': no_center_depts,
        })
