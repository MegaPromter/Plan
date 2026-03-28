# Миксины для проверки аутентификации и прав доступа на уровне view
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Получение объекта или автоматический возврат 404 при его отсутствии
from django.shortcuts import get_object_or_404

# Утилита для создания URL-адресов «ленивым» способом (вычисляется при обращении)
from django.urls import reverse_lazy
from django.utils import timezone

# Базовые generic-view классы Django
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

# Формы для создания и редактирования объектов
from .forms import EmployeeForm, KPIForm, VacationForm

# Модели приложения employees
from .models import KPI, Employee, Vacation

# ── Миксин: только admin ──────────────────────────────────────────────────────

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    # Разрешает доступ только пользователям с ролью 'admin'
    def test_func(self):
        try:
            # Сравниваем роль сотрудника с константой ROLE_ADMIN
            return self.request.user.employee.role == Employee.ROLE_ADMIN
        except Employee.DoesNotExist:
            # Если профиля Employee нет — разрешаем суперпользователям
            return self.request.user.is_superuser


# ── Миксин: writer-роли (могут редактировать) ─────────────────────────────────

class WriterRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    # Разрешает доступ пользователям с правом записи (is_writer=True)
    def test_func(self):
        try:
            # Проверяем флаг is_writer у связанного профиля Employee
            return self.request.user.employee.is_writer
        except Employee.DoesNotExist:
            # Если профиля нет — разрешаем суперпользователям
            return self.request.user.is_superuser


# ── Сотрудники ────────────────────────────────────────────────────────────────

class EmployeeListView(LoginRequiredMixin, ListView):
    # Модель, из которой берётся queryset
    model               = Employee
    # Шаблон для отображения списка сотрудников
    template_name       = 'employees/list.html'
    # Имя переменной в контексте шаблона
    context_object_name = 'employees'
    # Количество записей на одной странице
    paginate_by         = 30

    def get_queryset(self):
        # Базовый queryset с JOIN'ами по связанным объектам (избегаем N+1 запросов)
        qs = Employee.objects.select_related(
            'department', 'sector', 'ntc_center', 'user',
        )
        # Поиск по фамилии или имени (GET-параметр q)
        q = self.request.GET.get('q', '').strip()
        if q:
            # Объединяем два queryset через оператор | (OR)
            qs = qs.filter(last_name__icontains=q) | qs.filter(first_name__icontains=q)
        # Фильтр по коду отдела (GET-параметр dept)
        dept = self.request.GET.get('dept')
        if dept:
            qs = qs.filter(department__code=dept)
        # Алфавитная сортировка: фамилия, затем имя
        return qs.order_by('last_name', 'first_name')


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    # Детальная страница одного сотрудника
    model         = Employee
    template_name = 'employees/detail.html'

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Последние 10 отпусков сотрудника (для блока на странице)
        ctx['vacations'] = self.object.vacations.order_by('-date_start')[:10]
        # Последние 12 месяцев KPI (для таблицы показателей)
        ctx['kpis']      = self.object.kpis.order_by('-year', '-month')[:12]
        return ctx


class EmployeeCreateView(AdminRequiredMixin, CreateView):
    # Создание нового сотрудника — только для admin
    model         = Employee
    form_class    = EmployeeForm
    template_name = 'employees/form.html'
    # После создания перенаправляем на список сотрудников
    success_url   = reverse_lazy('employees:list')


class EmployeeUpdateView(WriterRequiredMixin, UpdateView):
    # Редактирование профиля сотрудника — для writer-ролей
    model         = Employee
    form_class    = EmployeeForm
    template_name = 'employees/form.html'

    def get_success_url(self):
        # После редактирования возвращаем на детальную страницу сотрудника
        return reverse_lazy('employees:detail', kwargs={'pk': self.object.pk})


# ── Отпуска ────────────────────────────────────────────────────────────────────

class VacationPlanView(LoginRequiredMixin, ListView):
    """Глобальный план отпусков — все сотрудники."""
    # Модель для отображения всех отпусков
    model               = Vacation
    # Шаблон таблицы/календаря отпусков
    template_name       = 'employees/vacation_plan_spa.html'
    # Имя переменной в контексте шаблона
    context_object_name = 'vacations'
    # Количество записей на странице
    paginate_by         = 50

    def get_queryset(self):
        # Загружаем с JOIN'ами по сотруднику и его отделу
        qs = Vacation.objects.select_related(
            'employee', 'employee__department',
        ).order_by('date_start', 'employee__last_name')
        # Фильтр по коду отдела
        dept = self.request.GET.get('dept', '').strip()
        if dept:
            qs = qs.filter(employee__department__code=dept)
        # Полнотекстовый поиск по фамилии или имени сотрудника
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(employee__last_name__icontains=q) | \
                 qs.filter(employee__first_name__icontains=q)
        # Фильтр по году начала отпуска
        year = self.request.GET.get('year', '').strip()
        if year:
            qs = qs.filter(date_start__year=year)
        return qs

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Список всех отделов для фильтра (используем динамический импорт)
        ctx['departments'] = __import__('apps.employees.models', fromlist=['Department']).Department.objects.all()
        # Текущий год для инициализации фильтра
        ctx['current_year'] = timezone.now().date().year
        # Диапазон годов для переключателя (2 прошлых + текущий + 2 будущих)
        ctx['years'] = list(range(ctx['current_year'] - 2, ctx['current_year'] + 3))
        return ctx


class VacationListView(LoginRequiredMixin, ListView):
    # Список отпусков конкретного сотрудника
    model               = Vacation
    template_name       = 'employees/vacation_list.html'
    context_object_name = 'vacations'

    def get_queryset(self):
        # Получаем сотрудника по emp_pk из URL (404 если не найден)
        self.employee = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        # Возвращаем отпуска только этого сотрудника, последние первыми
        return Vacation.objects.filter(employee=self.employee).order_by('-date_start')

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Передаём объект сотрудника в шаблон (для отображения имени в заголовке)
        ctx['employee'] = self.employee
        return ctx


class VacationCreateView(WriterRequiredMixin, CreateView):
    # Добавление нового отпуска сотруднику
    model         = Vacation
    form_class    = VacationForm
    template_name = 'employees/vacation_form.html'

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Передаём объект сотрудника в шаблон (для отображения имени в заголовке)
        ctx['employee'] = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        return ctx

    def form_valid(self, form):
        # Получаем сотрудника из URL и привязываем к новому отпуску
        employee = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        # Устанавливаем FK до сохранения формы
        form.instance.employee = employee
        # Сохраняем через родительский метод
        return super().form_valid(form)

    def get_success_url(self):
        # После создания возвращаем на список отпусков данного сотрудника
        return reverse_lazy('employees:vacation_list',
                            kwargs={'emp_pk': self.kwargs['emp_pk']})


class VacationUpdateView(WriterRequiredMixin, UpdateView):
    # Редактирование записи об отпуске
    model         = Vacation
    form_class    = VacationForm
    template_name = 'employees/vacation_form.html'

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Передаём объект сотрудника в шаблон
        ctx['employee'] = self.object.employee
        return ctx

    def get_success_url(self):
        # После редактирования возвращаем на список отпусков сотрудника
        return reverse_lazy('employees:vacation_list',
                            kwargs={'emp_pk': self.object.employee_id})


class VacationDeleteView(WriterRequiredMixin, DeleteView):
    # Удаление записи об отпуске
    model         = Vacation
    # Шаблон подтверждения удаления
    template_name = 'employees/vacation_confirm_delete.html'
    # Имя объекта в контексте шаблона для подтверждения
    context_object_name = 'vacation'

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Передаём сотрудника для отображения в сообщении подтверждения
        ctx['employee'] = self.object.employee
        return ctx

    def get_success_url(self):
        # После удаления возвращаем на список отпусков сотрудника
        return reverse_lazy('employees:vacation_list',
                            kwargs={'emp_pk': self.object.employee_id})


# ── KPI ────────────────────────────────────────────────────────────────────────

class KPIListView(LoginRequiredMixin, ListView):
    # Список всех KPI-записей сотрудника
    model               = KPI
    template_name       = 'employees/kpi_list.html'
    context_object_name = 'kpis'

    def get_queryset(self):
        # Получаем сотрудника по emp_pk из URL (404 если не найден)
        self.employee = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        # Возвращаем KPI только этого сотрудника, последние периоды первыми
        return KPI.objects.filter(employee=self.employee).order_by('-year', '-month')

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Передаём объект сотрудника в шаблон
        ctx['employee'] = self.employee
        return ctx


class KPICreateView(WriterRequiredMixin, CreateView):
    # Добавление новой KPI-записи за период
    model         = KPI
    form_class    = KPIForm
    template_name = 'employees/kpi_form.html'

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Передаём объект сотрудника в шаблон (для заголовка формы)
        ctx['employee'] = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        return ctx

    def form_valid(self, form):
        # Получаем сотрудника из URL и привязываем к новой записи KPI
        employee = get_object_or_404(Employee, pk=self.kwargs['emp_pk'])
        # Устанавливаем FK до сохранения формы
        form.instance.employee = employee
        # Сохраняем через родительский метод (вызовет KPI.save() с расчётом completion_pct)
        return super().form_valid(form)

    def get_success_url(self):
        # После создания возвращаем на список KPI данного сотрудника
        return reverse_lazy('employees:kpi_list',
                            kwargs={'emp_pk': self.kwargs['emp_pk']})


class KPIUpdateView(WriterRequiredMixin, UpdateView):
    # Редактирование существующей записи KPI
    model         = KPI
    form_class    = KPIForm
    template_name = 'employees/kpi_form.html'

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Передаём объект сотрудника в шаблон (для заголовка формы)
        ctx['employee'] = self.object.employee
        return ctx

    def get_success_url(self):
        # После редактирования возвращаем на список KPI сотрудника
        return reverse_lazy('employees:kpi_list',
                            kwargs={'emp_pk': self.object.employee_id})
