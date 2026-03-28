"""
API загрузки и мощности отделов.

GET /api/enterprise/capacity/ — загрузка по отделам (потребная vs располагаемая мощность)
    ?project_id=N — фильтр по проекту
    ?year=2026    — год (по умолчанию текущий)
    ?mode=staff|actual — режим расчёта мощности (штатная / фактическая)
"""
import logging
from datetime import date
from decimal import Decimal

from django.db.models import Sum, Q
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import LoginRequiredJsonMixin
from apps.employees.models import Department, Employee
from apps.works.models import Work, WorkCalendar

logger = logging.getLogger(__name__)


class CapacityView(LoginRequiredJsonMixin, View):
    """GET /api/enterprise/capacity/ — расчёт загрузки по отделам."""

    def get(self, request):
        try:
            year = int(request.GET.get('year', date.today().year))
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Невалидный год'}, status=400)
        project_id = request.GET.get('project_id')
        mode = request.GET.get('mode', 'actual')
        if mode not in ('staff', 'actual'):
            mode = 'actual'

        # Часовой фонд за год (из производственного календаря)
        calendar_hours = WorkCalendar.objects.filter(year=year).aggregate(
            total=Sum('hours_norm'),
        )['total'] or Decimal('0')

        departments = Department.objects.all().order_by('name')
        result = []

        for dept in departments:
            # --- Располагаемая мощность ---
            if mode == 'staff':
                headcount = dept.staff_count or 0
            else:
                headcount = Employee.objects.filter(
                    department=dept, is_active=True,
                ).count()

            capacity = float(calendar_hours) * headcount  # часов в году

            # --- Потребная трудоёмкость ---
            work_filter = Q(
                executor__department=dept,
                date_end__year=year,
            )
            if project_id:
                work_filter &= (
                    Q(pp_project__up_project_id=project_id)
                    | Q(project_id=project_id)
                )

            demand = Work.objects.filter(work_filter).aggregate(
                total=Sum('labor'),
            )['total'] or Decimal('0')

            # --- Процент загрузки ---
            loading_pct = (
                float(demand) / capacity * 100
                if capacity > 0 else 0
            )

            # Порог: <60 серый, 60-80 зелёный, 80-100 жёлтый, >100 красный
            if loading_pct < 60:
                level = 'low'
            elif loading_pct < 80:
                level = 'normal'
            elif loading_pct <= 100:
                level = 'high'
            else:
                level = 'overload'

            result.append({
                'department_id': dept.id,
                'department_name': dept.name or dept.code,
                'headcount': headcount,
                'capacity_hours': round(capacity, 2),
                'demand_hours': round(float(demand), 2),
                'loading_pct': round(loading_pct, 1),
                'level': level,
            })

        return JsonResponse({'year': year, 'mode': mode, 'departments': result})
