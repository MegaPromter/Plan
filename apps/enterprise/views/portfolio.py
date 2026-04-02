"""
API портфеля проектов (enterprise-расширение).

GET    /api/enterprise/portfolio/              — список проектов со статусами и загрузкой
PUT    /api/enterprise/portfolio/<id>/         — обновление enterprise-полей проекта
POST   /api/enterprise/portfolio/<id>/priority/ — установка приоритета
"""
import logging

from django.db.models import Count, DecimalField, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.views import View

from apps.api.mixins import (
    AdminRequiredJsonMixin,
    LoginRequiredJsonMixin,
    WriterRequiredJsonMixin,
    parse_json_body,
)
from apps.employees.models import Employee
from apps.works.models import Project, Work

logger = logging.getLogger(__name__)


def _serialize_portfolio_project(proj):
    """Сериализация проекта для портфеля (без N+1 — данные из annotate)."""
    chief = proj.chief_designer
    return {
        'id': proj.id,
        'name_full': proj.name_full or '',
        'name_short': proj.name_short or '',
        'code': proj.code or '',
        'status': proj.status,
        'priority_number': proj.priority_number,
        'priority_category': proj.priority_category or '',
        'chief_designer': {
            'id': chief.id,
            'name': str(chief),
        } if chief else None,
        'pp_count': getattr(proj, '_pp_count', 0),
        'sp_count': getattr(proj, '_sp_count', 0),
        'labor_total': float(getattr(proj, '_labor_total', 0) or 0),
        'created_at': proj.created_at.isoformat() if proj.created_at else '',
    }


def _annotate_portfolio(qs):
    """
    Добавляет к QuerySet проектов три подзапроса через Subquery.
    Такой подход позволяет получить агрегаты за ОДИН SQL-запрос вместо N+1.

    Subquery работает как коррелированный подзапрос: для каждого Project
    выполняется вложенный SELECT, связанный через OuterRef('pk').

    - pp_count: количество строк ПП (Work.show_in_pp=True), связанных через
      pp_project.up_project → Project. Нужен group by + COUNT, поэтому
      используется .values(...).annotate(...).values('c')[:1]
      (трюк с [:1] даёт LIMIT 1 для одного скалярного значения).

    - sp_count: количество задач СП (Work.show_in_plan=True), связанных напрямую
      через project_id → Project.pk.

    - labor_total: сумма трудозатрат по всем работам проекта (и ПП, и СП).
      Используем Q(... | ...) чтобы охватить оба источника.

    Coalesce(subquery, Value(0)) заменяет NULL на 0 — если у проекта нет работ,
    подзапрос вернёт NULL, а не 0.
    """
    # Считаем строки ПП, привязанные к проекту через PPProject.up_project
    pp_count_sq = Subquery(
        Work.objects.filter(
            pp_project__up_project=OuterRef('pk'), show_in_pp=True,
        ).order_by().values('pp_project__up_project').annotate(c=Count('id')).values('c')[:1],
        output_field=IntegerField(),
    )
    # Считаем задачи СП, напрямую привязанные к проекту
    sp_count_sq = Subquery(
        Work.objects.filter(
            project=OuterRef('pk'), show_in_plan=True,
        ).order_by().values('project').annotate(c=Count('id')).values('c')[:1],
        output_field=IntegerField(),
    )
    # Суммируем трудозатраты по всем работам проекта (ПП + СП)
    labor_sq = Subquery(
        Work.objects.filter(
            Q(pp_project__up_project=OuterRef('pk')) | Q(project=OuterRef('pk')),
        ).order_by().values('pk').annotate(s=Sum('labor')).values('s')[:1],
        output_field=DecimalField(),
    )
    return qs.annotate(
        _pp_count=Coalesce(pp_count_sq, Value(0), output_field=IntegerField()),
        _sp_count=Coalesce(sp_count_sq, Value(0), output_field=IntegerField()),
        _labor_total=Coalesce(labor_sq, Value(0), output_field=DecimalField()),
    )


class PortfolioListView(LoginRequiredJsonMixin, View):
    """GET /api/enterprise/portfolio/ — портфель проектов."""

    def get(self, request):
        qs = Project.objects.select_related('chief_designer').order_by(
            'priority_number', 'name_full',
        )

        # Фильтр по статусу
        status = request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        # Фильтр по категории приоритета
        priority = request.GET.get('priority_category')
        if priority:
            qs = qs.filter(priority_category=priority)

        qs = _annotate_portfolio(qs)
        projects = [_serialize_portfolio_project(p) for p in qs]
        return JsonResponse({'projects': projects})


class PortfolioDetailView(WriterRequiredJsonMixin, View):
    """PUT /api/enterprise/portfolio/<id>/ — обновление enterprise-полей."""

    def put(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            proj = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return JsonResponse({'error': 'Проект не найден'}, status=404)

        ALLOWED = {
            'status', 'priority_number', 'priority_category', 'chief_designer_id',
        }
        update_fields = []
        for field in ALLOWED:
            if field in data:
                val = data[field]
                if field == 'status':
                    valid_statuses = [c[0] for c in Project.STATUS_CHOICES]
                    if val not in valid_statuses:
                        return JsonResponse(
                            {'error': f'Недопустимый статус: {val}'}, status=400,
                        )
                if field == 'priority_category' and val:
                    valid_cats = [c[0] for c in Project.PRIORITY_CHOICES]
                    if val not in valid_cats:
                        return JsonResponse(
                            {'error': f'Недопустимая категория: {val}'}, status=400,
                        )
                if field == 'chief_designer_id' and val:
                    if not Employee.objects.filter(pk=val).exists():
                        return JsonResponse(
                            {'error': 'Сотрудник не найден'}, status=404,
                        )
                setattr(proj, field, val)
                update_fields.append(field)

        if update_fields:
            proj.save(update_fields=update_fields)

        # Перезагрузим с аннотациями для ответа
        proj = _annotate_portfolio(
            Project.objects.select_related('chief_designer').filter(pk=pk),
        ).first()

        return JsonResponse({
            'ok': True,
            'project': _serialize_portfolio_project(proj),
        })


class PortfolioPriorityView(AdminRequiredJsonMixin, View):
    """POST /api/enterprise/portfolio/<id>/priority/ — установка приоритета."""

    def post(self, request, pk):
        data = parse_json_body(request)
        if data is None:
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        try:
            proj = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return JsonResponse({'error': 'Проект не найден'}, status=404)

        proj.priority_number = data.get('priority_number')
        proj.priority_category = data.get('priority_category', '')
        proj.save(update_fields=['priority_number', 'priority_category'])

        proj = _annotate_portfolio(
            Project.objects.select_related('chief_designer').filter(pk=pk),
        ).first()

        return JsonResponse({
            'ok': True,
            'project': _serialize_portfolio_project(proj),
        })
