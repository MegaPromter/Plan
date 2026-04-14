# Миксины для проверки аутентификации и прав доступа на уровне view
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# timezone — работа со временем с учётом часового пояса
from django.utils import timezone

# Базовые generic-view классы Django
from django.views.generic import ListView, TemplateView

# Модели сотрудников — нужны для получения роли, настроек пользователя и списка отделов
from apps.employees.models import Department, Employee, RoleDelegation, Vacation

# Общий миксин для SPA-страниц
from .mixins import SPAContextMixin

# Основные модели данного приложения
from .models import Notice

# ── Журнал извещений ──────────────────────────────────────────────────────────


class NoticeListView(LoginRequiredMixin, SPAContextMixin, ListView):
    # Модель журнала извещений
    model = Notice
    # Шаблон списка извещений
    template_name = "works/notice_list.html"
    # Имя переменной в контексте шаблона
    context_object_name = "notices"
    # Количество записей на странице
    paginate_by = 30
    include_col_settings = True

    def get_queryset(self):
        # Загружаем извещения с JOIN'ами по отделу и исполнителю
        qs = Notice.objects.select_related("department", "sector", "executor")
        # Фильтр по статусу (активные / закрытые)
        status = self.request.GET.get("status")
        if status in {c[0] for c in Notice.STATUS_CHOICES}:
            qs = qs.filter(status=status)
        # Сортировка: самые свежие извещения первыми
        return qs.order_by("-date_issued")


# ── План/Отчёт SPA ──────────────────────────────────────────────────────────


class PlanSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """Главная SPA-страница «План/Отчёт»."""

    template_name = "works/plan_spa.html"
    include_col_settings = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Список кодов отделов для мгновенного рендера dept-dropdown без ожидания API
        import json as _json

        ctx["dept_codes_json"] = _json.dumps(
            list(Department.objects.order_by("code").values_list("code", flat=True))
        )
        return ctx


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    # Разрешает доступ только администраторам (роль 'admin') и суперпользователям
    def test_func(self):
        try:
            # Проверяем роль сотрудника
            return self.request.user.employee.role == "admin"
        except Exception:
            # При любой ошибке (нет профиля и т.д.) — проверяем is_superuser
            return self.request.user.is_superuser


class ProjectsSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Управление проектами» (чтение — все, редактирование — admin через API)."""

    template_name = "works/projects_spa.html"


class ProductionPlanSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Производственный план»."""

    template_name = "works/production_plan_spa.html"
    include_col_settings = True


class BusinessTripsSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «План командировок»."""

    template_name = "works/business_trips_spa.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx["current_year"] = current_year
        ctx["years"] = list(range(current_year - 3, current_year + 4))
        return ctx


class WorkCalendarSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Производственный календарь»."""

    template_name = "works/work_calendar_spa.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx["current_year"] = current_year
        ctx["years"] = list(range(current_year - 3, current_year + 4))
        return ctx


class AuditLogSPAView(AdminRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Журнал аудита» (только admin)."""

    template_name = "works/audit_log_spa.html"


class AnalyticsWorkloadSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Загрузка сотрудников» (аналитика)."""

    template_name = "works/analytics_workload_spa.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx["current_year"] = current_year
        ctx["years"] = list(range(current_year - 3, current_year + 4))
        return ctx


class AnalyticsEmployeeSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Доска сотрудника» (персональная аналитика)."""

    template_name = "works/analytics_employee_spa.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx["current_year"] = current_year
        ctx["years"] = list(range(current_year - 3, current_year + 4))
        emp = getattr(self.request.user, "employee", None)
        ctx["current_employee_id"] = emp.pk if emp else 0
        ctx["is_writer_flag"] = emp.is_writer if emp else False
        return ctx


class AnalyticsPPSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Отчёты ПП» (аналитика производственного плана)."""

    template_name = "works/analytics_pp_spa.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx["current_year"] = current_year
        ctx["years"] = list(range(current_year - 3, current_year + 4))
        return ctx


class AnalyticsSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """Единая SPA-страница аналитики с иерархическим drill-down."""

    template_name = "works/analytics_spa.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx["current_year"] = current_year
        return ctx


# ── Демо-страницы (только DEBUG) ────────────────────────────────────────────
class DemoDensityView(TemplateView):
    """Демо: переключатель плотности таблицы."""

    template_name = "demo/demo_density.html"


class DemoSkeletonView(TemplateView):
    """Демо: skeleton-загрузка."""

    template_name = "demo/demo_skeleton.html"


class DemoSlideoutView(TemplateView):
    """Демо: slideout-панель vs. модальное окно."""

    template_name = "demo/demo_slideout.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx["current_year"] = current_year
        ctx["years"] = list(range(current_year - 3, current_year + 4))
        return ctx


class DemoTripsView(TemplateView):
    """Демо: варианты оформления плана командировок."""

    def get_template_names(self):
        n = self.kwargs.get("num", 1)
        return [f"demo/demo_trips_{n}.html"]


class DemoPPFilterView(TemplateView):
    """Демо: варианты фильтра отчётов в ПП."""

    def get_template_names(self):
        n = self.kwargs.get("num", 1)
        return [f"demo/demo_pp_filter_{n}.html"]


class ReportsSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """Редирект /works/reports/ → /works/analytics/ (обратная совместимость)."""

    def get(self, request, *args, **kwargs):
        from django.shortcuts import redirect

        return redirect("works:analytics")


class FeedbackSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """Замечания и предложения."""

    template_name = "works/feedback_spa.html"


class DelegationsSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Делегирование прав»."""

    template_name = "works/delegations_spa.html"

    def get_context_data(self, **kwargs):
        import json as _json

        ctx = super().get_context_data(**kwargs)
        emp = getattr(self.request.user, "employee", None)
        if emp:
            col = emp.col_settings or {}
            ctx["auto_delegate_enabled"] = col.get("auto_delegate_enabled", False)
            ctx["auto_delegate_employee_id"] = col.get(
                "auto_delegate_employee_id", None
            )
            # Scope по умолчанию для формы создания (по роли)
            scope = None
            role = emp.role
            if role in ("ntc_head", "ntc_deputy") and emp.ntc_center:
                scope = ("center", emp.ntc_center.code)
            elif role in ("dept_head", "dept_deputy") and emp.department:
                scope = ("dept", emp.department.code)
            elif role == "sector_head" and emp.sector:
                scope = ("sector", emp.sector.code)
            elif emp.department:
                scope = ("dept", emp.department.code)
            ctx["default_scope_type"] = scope[0] if scope else ""
            ctx["default_scope_value"] = scope[1] if scope else ""

            # Список всех активных сотрудников для dropdown (исключая себя)
            employees = list(
                Employee.objects.filter(is_active=True)
                .exclude(pk=emp.pk)
                .order_by("last_name", "first_name")
                .values("pk", "last_name", "first_name", "patronymic")
            )
            ctx["employees_json"] = _json.dumps(
                [
                    {
                        "id": e["pk"],
                        "full_name": " ".join(
                            filter(
                                None,
                                [e["last_name"], e["first_name"], e["patronymic"]],
                            )
                        ),
                    }
                    for e in employees
                ]
            )

            # Предстоящие отпуска текущего пользователя
            today = timezone.now().date()
            upcoming = list(
                Vacation.objects.filter(employee=emp, date_end__gte=today).order_by(
                    "date_start"
                )
            )
            # ID отпусков, для которых уже есть автоделегирование
            vac_ids_with_deleg = (
                set(
                    RoleDelegation.objects.filter(
                        source_vacation_id__in=[v.pk for v in upcoming]
                    ).values_list("source_vacation_id", flat=True)
                )
                if upcoming
                else set()
            )
            ctx["my_vacations_json"] = _json.dumps(
                [
                    {
                        "id": v.pk,
                        "vac_type": v.vac_type,
                        "vac_type_display": v.get_vac_type_display(),
                        "date_start": v.date_start.isoformat(),
                        "date_end": v.date_end.isoformat(),
                        "duration_days": v.duration_days,
                        "notes": v.notes,
                        "has_delegation": v.pk in vac_ids_with_deleg,
                    }
                    for v in upcoming
                ]
            )
        else:
            ctx["employees_json"] = "[]"
            ctx["my_vacations_json"] = "[]"
        return ctx


class EnterpriseSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Управление предприятием»."""

    template_name = "enterprise/enterprise_stub.html"

    def get_context_data(self, **kwargs):
        import json as _json

        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx["current_year"] = current_year
        ctx["years"] = list(range(current_year - 3, current_year + 4))
        # Сотрудники для селектов «Главный конструктор»
        emps = list(
            Employee.objects.filter(is_active=True)
            .order_by("last_name", "first_name")
            .values("id", "last_name", "first_name", "patronymic")
        )
        employees_list = []
        for e in emps:
            ln = e["last_name"] or ""
            fn = (e["first_name"] or "")[:1]
            pat = (e["patronymic"] or "")[:1]
            name = f"{ln} {fn}.{pat}." if pat else f"{ln} {fn}."
            employees_list.append({"id": e["id"], "name": name.strip()})
        ctx["employees_json"] = _json.dumps(employees_list, ensure_ascii=False).replace(
            "</", "<\\/"
        )
        return ctx


class ERDiagramView(TemplateView):
    """ER-диаграмма моделей приложения (standalone, без base.html)."""

    template_name = "demo/er_diagram.html"
