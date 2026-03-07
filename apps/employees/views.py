from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView,
)
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404

from .models import Employee, Vacation, KPI
from .forms  import EmployeeForm, VacationForm, KPIForm


# ── Миксин: только admin ──────────────────────────────────────────────────────

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        try:
            return self.request.user.employee.role == Employee.ROLE_ADMIN
        except Employee.DoesNotExist:
            return self.request.user.is_superuser


# ── Миксин: writer-роли (могут редактировать) ─────────────────────────────────

class WriterRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        try:
            return self.request.user.employee.is_writer
        except Employee.DoesNotExist:
            return self.request.user.is_superuser


# ── Сотрудники ────────────────────────────────────────────────────────────────

class EmployeeListView(LoginRequiredMixin, ListView):
    model               = Employee
    template_name       = 'employees/list.html'
    context_object_name = 'employees'
    paginate_by         = 30

    def get_queryset(self):
        qs = Employee.objects.select_related(
            'department', 'sector', 'ntc_center', 'user',
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(last_name__icontains=q) | qs.filter(first_name__icontains=q)
        dept = self.request.GET.get('dept')
        if dept:
            qs = qs.filter(department__code=dept)
        return qs.order_by('last_name', 'first_name')


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    model         = Employee
    template_name = 'employees/detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['vacations'] = self.object.vacations.order_by('-date_start')[:10]
        ctx['kpis']      = self.object.kpis.order_by('-year', '-month')[:12]
        return ctx


class EmployeeCreateView(AdminRequiredMixin, CreateView):
    model         = Employee
    form_class    = EmployeeForm
    template_name = 'employees/form.html'
    success_url   = reverse_lazy('employees:list')


class EmployeeUpdateView(WriterRequiredMixin, UpdateView):
    model         = Employee
    form_class    = EmployeeForm
    template_name = 'employees/form.html'

    def get_success_url(self):
        return reverse_lazy('employees:detail', kwargs={'pk': self.object.pk})


# ── Отпуска ────────────────────────────────────────────────────────────────────

class VacationPlanView(LoginRequiredMixin, ListView):
    """Глобальный план отпусков — все сотрудники."""
    model               = Vacation
    template_name       = 'employees/vacation_plan.html'
    context_object_name = 'vacations'
    paginate_by         = 50

    def get_queryset(self):
        qs = Vacation.objects.select_related(
            'employee', 'employee__department',
        ).order_by('date_start', 'employee__last_name')
        dept = self.request.GET.get('dept', '').strip()
        if dept:
            qs = qs.filter(employee__department__code=dept)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(employee__last_name__icontains=q) | \
                 qs.filter(employee__first_name__icontains=q)
        year = self.request.GET.get('year', '').strip()
        if year:
            qs = qs.filter(date_start__year=year)
        return qs

    def get_context_data(self, **kwargs):
        from datetime import date
        ctx = super().get_context_data(**kwargs)
        ctx['departments'] = __import__('apps.employees.models', fromlist=['Department']).Department.objects.all()
        ctx['current_year'] = date.today().year
        ctx['years'] = list(range(ctx['current_year'] - 2, ctx['current_year'] + 3))
        return ctx


class VacationListView(LoginRequiredMixin, ListView):
    model               = Vacation
    template_name       = 'employees/vacation_list.html'
    context_object_name = 'vacations'

    def get_queryset(self):
        self.employee = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        return Vacation.objects.filter(employee=self.employee).order_by('-date_start')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employee'] = self.employee
        return ctx


class VacationCreateView(WriterRequiredMixin, CreateView):
    model         = Vacation
    form_class    = VacationForm
    template_name = 'employees/vacation_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employee'] = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        return ctx

    def form_valid(self, form):
        employee = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        form.instance.employee = employee
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('employees:vacation_list',
                            kwargs={'emp_pk': self.kwargs['emp_pk']})


class VacationUpdateView(WriterRequiredMixin, UpdateView):
    model         = Vacation
    form_class    = VacationForm
    template_name = 'employees/vacation_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employee'] = self.object.employee
        return ctx

    def get_success_url(self):
        return reverse_lazy('employees:vacation_list',
                            kwargs={'emp_pk': self.object.employee_id})


class VacationDeleteView(WriterRequiredMixin, DeleteView):
    model         = Vacation
    template_name = 'employees/vacation_confirm_delete.html'
    context_object_name = 'vacation'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employee'] = self.object.employee
        return ctx

    def get_success_url(self):
        return reverse_lazy('employees:vacation_list',
                            kwargs={'emp_pk': self.object.employee_id})


# ── KPI ────────────────────────────────────────────────────────────────────────

class KPIListView(LoginRequiredMixin, ListView):
    model               = KPI
    template_name       = 'employees/kpi_list.html'
    context_object_name = 'kpis'

    def get_queryset(self):
        self.employee = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        return KPI.objects.filter(employee=self.employee).order_by('-year', '-month')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employee'] = self.employee
        return ctx


class KPICreateView(WriterRequiredMixin, CreateView):
    model         = KPI
    form_class    = KPIForm
    template_name = 'employees/kpi_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employee'] = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        return ctx

    def form_valid(self, form):
        employee = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        form.instance.employee = employee
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('employees:kpi_list',
                            kwargs={'emp_pk': self.kwargs['emp_pk']})


class KPIUpdateView(WriterRequiredMixin, UpdateView):
    model         = KPI
    form_class    = KPIForm
    template_name = 'employees/kpi_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employee'] = self.object.employee
        return ctx

    def get_success_url(self):
        return reverse_lazy('employees:kpi_list',
                            kwargs={'emp_pk': self.object.employee_id})
