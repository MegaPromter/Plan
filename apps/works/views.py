# Миксины для проверки аутентификации и прав доступа на уровне view
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
# Базовые generic-view классы Django
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView,
)
# Утилита для создания URL-адресов «ленивым» способом (вычисляется при обращении)
from django.urls import reverse_lazy
# Получение объекта или автоматический возврат 404 при его отсутствии
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.db.models import Q

# Модель сотрудника — нужна для получения роли и настроек пользователя
from apps.employees.models import Employee
# Модель отдела — используется в контексте для фильтрации по отделам
from apps.employees.models import Department
# Единый фильтр видимости (с поддержкой RoleDelegation и show_all_depts)
from apps.api.utils import get_visibility_filter
# Основные модели данного приложения
from .models import Work, WorkReport, Notice
# Формы для создания и редактирования объектов
from .forms  import WorkForm, WorkReportForm, NoticeForm
# Общий миксин для SPA-страниц
from .mixins import SPAContextMixin
# timezone — работа со временем с учётом часового пояса
from django.utils import timezone


# ── Миксин writer ─────────────────────────────────────────────────────────────

class WriterRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    # Проверяет, имеет ли пользователь право на запись (is_writer=True)
    def test_func(self):
        try:
            # Проверяем флаг is_writer у связанного профиля Employee
            return self.request.user.employee.is_writer
        except Employee.DoesNotExist:
            # Если профиля Employee нет — разрешаем суперпользователям
            return self.request.user.is_superuser


# ── Работы ────────────────────────────────────────────────────────────────────

class WorkListView(LoginRequiredMixin, ListView):
    # Модель, из которой берётся queryset
    model               = Work
    # Шаблон для отображения списка работ
    template_name       = 'works/list.html'
    # Имя переменной в контексте шаблона
    context_object_name = 'works'
    # Количество записей на одной странице
    paginate_by         = 50

    def get_queryset(self):
        # Базовый queryset с оптимизированными JOIN'ами для связанных объектов
        qs = Work.objects.select_related(
            'department', 'sector',
            'ntc_center', 'executor', 'project',
        ).filter(get_visibility_filter(self.request.user))

        # Фильтры из GET-параметров
        # Фильтр по источнику (план задач или производственный план)
        src = self.request.GET.get('source')
        if src == 'task':
            qs = qs.filter(show_in_plan=True)
        elif src == 'pp':
            qs = qs.filter(show_in_pp=True)

        # Полнотекстовый поиск по названию работы, номеру документа, фамилии исполнителя
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(work_name__icontains=q) |
                Q(work_num__icontains=q) |
                Q(executor__last_name__icontains=q)
            )

        # Фильтр по коду отдела
        dept = self.request.GET.get('dept')
        if dept:
            qs = qs.filter(department__code=dept)

        # Фильтр по году: работы, активные в данном году
        year = self.request.GET.get('year')
        if year:
            qs = qs.filter(
                Q(date_start__year__lte=year, date_end__year__gte=year) |
                Q(date_start__year=year)
            )

        # Сортируем: последние созданные — первыми
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        # Вызываем родительский метод для стандартных контекстных переменных
        ctx = super().get_context_data(**kwargs)
        # Список всех отделов (для фильтра по отделу)
        ctx['departments'] = Department.objects.order_by('code')
        # Диапазон годов для фильтра (3 прошлых + текущий + 2 будущих)
        current_year = timezone.now().date().year
        ctx['years'] = list(range(current_year - 3, current_year + 3))
        return ctx


class WorkDetailView(LoginRequiredMixin, DetailView):
    # Модель для детального просмотра
    model         = Work
    # Шаблон детальной страницы работы
    template_name = 'works/detail.html'

    def get_queryset(self):
        # Применяем фильтр видимости + загружаем все связанные объекты одним запросом
        return Work.objects.filter(
            get_visibility_filter(self.request.user)
        ).select_related(
            'department', 'sector', 'ntc_center',
            'executor', 'project', 'created_by',
        ).prefetch_related('reports')  # Отчётные документы одним запросом


class WorkCreateView(WriterRequiredMixin, CreateView):
    # Модель для создания новой записи
    model         = Work
    # Форма для создания работы
    form_class    = WorkForm
    # Шаблон с формой
    template_name = 'works/form.html'

    def form_valid(self, form):
        try:
            # Автоматически устанавливаем создателя записи из профиля Employee
            form.instance.created_by = self.request.user.employee
        except Employee.DoesNotExist:
            # Если профиля Employee нет — оставляем created_by пустым
            pass
        # Передаём управление родительскому методу (сохранение + редирект)
        return super().form_valid(form)

    def get_success_url(self):
        # После создания перенаправляем на детальную страницу новой записи
        return reverse_lazy('works:detail', kwargs={'pk': self.object.pk})


class WorkUpdateView(WriterRequiredMixin, UpdateView):
    # Модель для редактирования
    model         = Work
    # Форма редактирования
    form_class    = WorkForm
    # Шаблон с формой
    template_name = 'works/form.html'

    def get_queryset(self):
        # Пользователь может редактировать только видимые ему записи
        return Work.objects.filter(get_visibility_filter(self.request.user))

    def get_success_url(self):
        # После редактирования возвращаем на детальную страницу
        return reverse_lazy('works:detail', kwargs={'pk': self.object.pk})


class WorkDeleteView(WriterRequiredMixin, DeleteView):
    # Модель для удаления
    model         = Work
    # Шаблон подтверждения удаления
    template_name = 'works/confirm_delete.html'
    # После удаления перенаправляем на список работ
    success_url   = reverse_lazy('works:list')

    def get_queryset(self):
        # Пользователь может удалять только видимые ему записи
        return Work.objects.filter(get_visibility_filter(self.request.user))


# ── Отчётные документы ────────────────────────────────────────────────────────

class ReportCreateView(WriterRequiredMixin, CreateView):
    # Модель отчётного документа
    model         = WorkReport
    # Форма для создания документа
    form_class    = WorkReportForm
    # Шаблон с формой
    template_name = 'works/report_form.html'

    def form_valid(self, form):
        # Получаем родительскую работу по work_pk из URL
        work = get_object_or_404(Work, pk=self.kwargs['work_pk'])
        # Привязываем новый документ к работе (work — обязательный FK)
        form.instance.work = work
        # Сохраняем через родительский метод
        return super().form_valid(form)

    def get_success_url(self):
        # Возвращаем на детальную страницу работы, к которой добавлен документ
        return reverse_lazy('works:detail', kwargs={'pk': self.kwargs['work_pk']})


class ReportUpdateView(WriterRequiredMixin, UpdateView):
    # Модель и форма редактирования документа
    model         = WorkReport
    form_class    = WorkReportForm
    # Шаблон с формой
    template_name = 'works/report_form.html'

    def get_success_url(self):
        # Возвращаем на детальную страницу родительской работы
        return reverse_lazy('works:detail', kwargs={'pk': self.object.work_id})


class ReportDeleteView(WriterRequiredMixin, DeleteView):
    # Модель для удаления документа
    model         = WorkReport
    # Шаблон подтверждения удаления
    template_name = 'works/confirm_delete.html'

    def get_success_url(self):
        # Возвращаем на детальную страницу родительской работы
        return reverse_lazy('works:detail', kwargs={'pk': self.object.work_id})


# ── Журнал извещений ──────────────────────────────────────────────────────────

class NoticeListView(LoginRequiredMixin, SPAContextMixin, ListView):
    # Модель журнала извещений
    model               = Notice
    # Шаблон списка извещений
    template_name       = 'works/notice_list.html'
    # Имя переменной в контексте шаблона
    context_object_name = 'notices'
    # Количество записей на странице
    paginate_by         = 30
    include_col_settings = True

    def get_queryset(self):
        # Загружаем извещения с JOIN'ами по отделу и исполнителю
        qs = Notice.objects.select_related('department', 'sector', 'executor')
        # Фильтр по статусу (активные / закрытые)
        status = self.request.GET.get('status')
        if status in {c[0] for c in Notice.STATUS_CHOICES}:
            qs = qs.filter(status=status)
        # Сортировка: самые свежие извещения первыми
        return qs.order_by('-date_issued')


class NoticeDetailView(LoginRequiredMixin, DetailView):
    # Детальная страница одного извещения
    model         = Notice
    template_name = 'works/notice_detail.html'

    def get_queryset(self):
        return Notice.objects.select_related('department', 'sector', 'executor')


class NoticeCreateView(WriterRequiredMixin, CreateView):
    model         = Notice
    form_class    = NoticeForm
    template_name = 'works/notice_form.html'
    success_url   = reverse_lazy('works:notice_list')

    def form_valid(self, form):
        messages.success(self.request, 'Извещение успешно создано.')
        return super().form_valid(form)


class NoticeUpdateView(WriterRequiredMixin, UpdateView):
    model         = Notice
    form_class    = NoticeForm
    template_name = 'works/notice_form.html'
    success_url   = reverse_lazy('works:notice_list')

    def form_valid(self, form):
        messages.success(self.request, 'Извещение успешно сохранено.')
        return super().form_valid(form)


# ── План/Отчёт SPA ──────────────────────────────────────────────────────────

class PlanSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """Главная SPA-страница «План/Отчёт»."""
    template_name = 'works/plan_spa.html'
    include_col_settings = True


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    # Разрешает доступ только администраторам (роль 'admin') и суперпользователям
    def test_func(self):
        try:
            # Проверяем роль сотрудника
            return self.request.user.employee.role == 'admin'
        except Exception:
            # При любой ошибке (нет профиля и т.д.) — проверяем is_superuser
            return self.request.user.is_superuser


class ProjectsSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Управление проектами» (чтение — все, редактирование — admin через API)."""
    template_name = 'works/projects_spa.html'


class ProductionPlanSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Производственный план»."""
    template_name = 'works/production_plan_spa.html'
    include_col_settings = True


class BusinessTripsSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «План командировок»."""
    template_name = 'works/business_trips_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx['current_year'] = current_year
        ctx['years'] = list(range(current_year - 3, current_year + 4))
        return ctx


class WorkCalendarSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Производственный календарь»."""
    template_name = 'works/work_calendar_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx['current_year'] = current_year
        ctx['years'] = list(range(current_year - 3, current_year + 4))
        return ctx


class AuditLogSPAView(AdminRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Журнал аудита» (только admin)."""
    template_name = 'works/audit_log_spa.html'


class AnalyticsWorkloadSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Загрузка сотрудников» (аналитика)."""
    template_name = 'works/analytics_workload_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx['current_year'] = current_year
        ctx['years'] = list(range(current_year - 3, current_year + 4))
        return ctx


class AnalyticsEmployeeSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Доска сотрудника» (персональная аналитика)."""
    template_name = 'works/analytics_employee_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx['current_year'] = current_year
        ctx['years'] = list(range(current_year - 3, current_year + 4))
        emp = getattr(self.request.user, 'employee', None)
        ctx['current_employee_id'] = emp.pk if emp else 0
        ctx['is_writer_flag'] = emp.is_writer if emp else False
        return ctx


class AnalyticsPPSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """SPA-страница «Отчёты ПП» (аналитика производственного плана)."""
    template_name = 'works/analytics_pp_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx['current_year'] = current_year
        ctx['years'] = list(range(current_year - 3, current_year + 4))
        return ctx


class AnalyticsSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """Единая SPA-страница аналитики с иерархическим drill-down."""
    template_name = 'works/analytics_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx['current_year'] = current_year
        return ctx


# ── Демо-страницы (только DEBUG) ────────────────────────────────────────────
class DemoDensityView(TemplateView):
    """Демо: переключатель плотности таблицы."""
    template_name = 'works/demo_density.html'

class DemoSkeletonView(TemplateView):
    """Демо: skeleton-загрузка."""
    template_name = 'works/demo_skeleton.html'

class DemoSlideoutView(TemplateView):
    """Демо: slideout-панель vs. модальное окно."""
    template_name = 'works/demo_slideout.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        current_year = timezone.now().date().year
        ctx['current_year'] = current_year
        ctx['years'] = list(range(current_year - 3, current_year + 4))
        return ctx


class DemoTripsView(TemplateView):
    """Демо: варианты оформления плана командировок."""
    def get_template_names(self):
        n = self.kwargs.get('num', 1)
        return [f'works/demo_trips_{n}.html']


class DemoPPFilterView(TemplateView):
    """Демо: варианты фильтра отчётов в ПП."""
    def get_template_names(self):
        n = self.kwargs.get('num', 1)
        return [f'works/demo_pp_filter_{n}.html']


class ReportsSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """Редирект /works/reports/ → /works/analytics/ (обратная совместимость)."""
    def get(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        return redirect('works:analytics')


class FeedbackSPAView(LoginRequiredMixin, SPAContextMixin, TemplateView):
    """Замечания и предложения."""
    template_name = 'works/feedback_spa.html'


class ERDiagramView(TemplateView):
    """ER-диаграмма моделей приложения (standalone, без base.html)."""
    template_name = 'works/er_diagram.html'
