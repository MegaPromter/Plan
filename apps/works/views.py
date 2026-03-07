from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin, AccessMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView,
)
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.db.models import Q
import json

from apps.employees.models import Employee
from apps.employees.models import Department
from .models import Work, WorkReport, Notice
from .forms  import WorkForm, WorkReportForm, NoticeForm
import datetime


# ── Миксин writer ─────────────────────────────────────────────────────────────

class WriterRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        try:
            return self.request.user.employee.is_writer
        except Employee.DoesNotExist:
            return self.request.user.is_superuser


# ── Вспомогательная функция: фильтр видимости ─────────────────────────────────

def visibility_filter(user) -> Q:
    """
    Возвращает Q-объект для фильтрации Work по роли пользователя.
    admin → без фильтра (Q())
    ntc_head/ntc_deputy → по ntc_center
    dept_head/dept_deputy → по department
    sector_head → по department + sector
    user → по executor или created_by
    """
    try:
        emp = user.employee
    except Employee.DoesNotExist:
        if user.is_superuser:
            return Q()
        return Q(pk__in=[])   # ничего не показываем

    role = emp.role

    if role == Employee.ROLE_ADMIN or user.is_superuser:
        return Q()

    if role in (Employee.ROLE_NTC_HEAD, Employee.ROLE_NTC_DEPUTY):
        return Q(ntc_center=emp.ntc_center)

    if role in (Employee.ROLE_DEPT_HEAD, Employee.ROLE_DEPT_DEPUTY):
        return Q(department=emp.department)

    if role == Employee.ROLE_SECTOR_HEAD:
        return Q(department=emp.department, sector=emp.sector)

    # ROLE_USER — только свои работы
    return Q(executor=emp) | Q(created_by=emp)


# ── Работы ────────────────────────────────────────────────────────────────────

class WorkListView(LoginRequiredMixin, ListView):
    model               = Work
    template_name       = 'works/list.html'
    context_object_name = 'works'
    paginate_by         = 50

    def get_queryset(self):
        qs = Work.objects.select_related(
            'work_type', 'department', 'sector',
            'ntc_center', 'executor', 'project',
        ).filter(visibility_filter(self.request.user))

        # Фильтры из GET-параметров
        src = self.request.GET.get('source')
        if src in (Work.SOURCE_TASK, Work.SOURCE_PP):
            qs = qs.filter(source_type=src)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(work_name__icontains=q) |
                Q(work_number__icontains=q) |
                Q(executor__last_name__icontains=q)
            )

        dept = self.request.GET.get('dept')
        if dept:
            qs = qs.filter(department__code=dept)

        year = self.request.GET.get('year')
        if year:
            qs = qs.filter(
                Q(date_start__year__lte=year, date_end__year__gte=year) |
                Q(date_start__year=year)
            )

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['source_choices'] = Work.SOURCE_CHOICES
        ctx['departments'] = Department.objects.order_by('code')
        current_year = datetime.date.today().year
        ctx['years'] = list(range(current_year - 3, current_year + 3))
        return ctx


class WorkDetailView(LoginRequiredMixin, DetailView):
    model         = Work
    template_name = 'works/detail.html'

    def get_queryset(self):
        return Work.objects.filter(
            visibility_filter(self.request.user)
        ).select_related(
            'work_type', 'department', 'sector', 'ntc_center',
            'executor', 'project', 'created_by',
            'task_detail', 'pp_detail',
        ).prefetch_related('reports')


class WorkCreateView(WriterRequiredMixin, CreateView):
    model         = Work
    form_class    = WorkForm
    template_name = 'works/form.html'

    def form_valid(self, form):
        try:
            form.instance.created_by = self.request.user.employee
        except Employee.DoesNotExist:
            pass
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('works:detail', kwargs={'pk': self.object.pk})


class WorkUpdateView(WriterRequiredMixin, UpdateView):
    model         = Work
    form_class    = WorkForm
    template_name = 'works/form.html'

    def get_queryset(self):
        return Work.objects.filter(visibility_filter(self.request.user))

    def get_success_url(self):
        return reverse_lazy('works:detail', kwargs={'pk': self.object.pk})


class WorkDeleteView(WriterRequiredMixin, DeleteView):
    model         = Work
    template_name = 'works/confirm_delete.html'
    success_url   = reverse_lazy('works:list')

    def get_queryset(self):
        return Work.objects.filter(visibility_filter(self.request.user))


# ── Отчётные документы ────────────────────────────────────────────────────────

class ReportCreateView(WriterRequiredMixin, CreateView):
    model         = WorkReport
    form_class    = WorkReportForm
    template_name = 'works/report_form.html'

    def form_valid(self, form):
        work = get_object_or_404(Work, pk=self.kwargs['work_pk'])
        form.instance.work = work
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('works:detail', kwargs={'pk': self.kwargs['work_pk']})


class ReportUpdateView(WriterRequiredMixin, UpdateView):
    model         = WorkReport
    form_class    = WorkReportForm
    template_name = 'works/report_form.html'

    def get_success_url(self):
        return reverse_lazy('works:detail', kwargs={'pk': self.object.work_id})


class ReportDeleteView(WriterRequiredMixin, DeleteView):
    model         = WorkReport
    template_name = 'works/confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('works:detail', kwargs={'pk': self.object.work_id})


# ── Журнал извещений ──────────────────────────────────────────────────────────

class NoticeListView(LoginRequiredMixin, ListView):
    model               = Notice
    template_name       = 'works/notice_list.html'
    context_object_name = 'notices'
    paginate_by         = 30

    def get_queryset(self):
        qs = Notice.objects.select_related('department', 'executor')
        status = self.request.GET.get('status')
        if status in (Notice.STATUS_ACTIVE, Notice.STATUS_CLOSED):
            qs = qs.filter(status=status)
        return qs.order_by('-date_issued')


class NoticeDetailView(LoginRequiredMixin, DetailView):
    model         = Notice
    template_name = 'works/notice_detail.html'


class NoticeCreateView(WriterRequiredMixin, CreateView):
    model         = Notice
    form_class    = NoticeForm
    template_name = 'works/notice_form.html'
    success_url   = reverse_lazy('works:notice_list')


class NoticeUpdateView(WriterRequiredMixin, UpdateView):
    model         = Notice
    form_class    = NoticeForm
    template_name = 'works/notice_form.html'
    success_url   = reverse_lazy('works:notice_list')


# ── План/Отчёт SPA ──────────────────────────────────────────────────────────

class PlanSPAView(LoginRequiredMixin, TemplateView):
    """Главная SPA-страница «План/Отчёт» — аналог Flask plan.html."""
    template_name = 'works/plan_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = getattr(self.request.user, 'employee', None)
        ctx['role'] = emp.role if emp else ('admin' if self.request.user.is_superuser else 'user')
        ctx['username'] = emp.short_name if emp else self.request.user.username
        ctx['is_writer'] = (emp.is_writer if emp else self.request.user.is_superuser)
        # Настройки ширин колонок
        col_settings = {}
        if emp and emp.col_settings:
            col_settings = emp.col_settings if isinstance(emp.col_settings, dict) else {}
        ctx['col_settings'] = json.dumps(col_settings)
        return ctx


class ProjectsSPAView(LoginRequiredMixin, TemplateView):
    """SPA-страница «Управление проектами»."""
    template_name = 'works/projects_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = getattr(self.request.user, 'employee', None)
        ctx['role'] = emp.role if emp else ('admin' if self.request.user.is_superuser else 'user')
        ctx['username'] = emp.short_name if emp else self.request.user.username
        ctx['is_writer'] = (emp.is_writer if emp else self.request.user.is_superuser)
        return ctx


class ProductionPlanSPAView(LoginRequiredMixin, TemplateView):
    """SPA-страница «Производственный план»."""
    template_name = 'works/production_plan_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = getattr(self.request.user, 'employee', None)
        ctx['role'] = emp.role if emp else ('admin' if self.request.user.is_superuser else 'user')
        ctx['username'] = emp.short_name if emp else self.request.user.username
        ctx['is_writer'] = (emp.is_writer if emp else self.request.user.is_superuser)
        return ctx


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        try:
            return self.request.user.employee.role == 'admin'
        except Exception:
            return self.request.user.is_superuser


class WorkCalendarSPAView(AdminRequiredMixin, TemplateView):
    """SPA-страница «Производственный календарь» — только для администратора."""
    template_name = 'works/work_calendar_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = getattr(self.request.user, 'employee', None)
        ctx['username'] = emp.short_name if emp else self.request.user.username
        current_year = datetime.date.today().year
        ctx['current_year'] = current_year
        ctx['years'] = list(range(current_year - 3, current_year + 4))
        return ctx
