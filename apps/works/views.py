# Миксины для проверки аутентификации и прав доступа на уровне view
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin, AccessMixin
# Базовые generic-view классы Django
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView,
)
# Утилита для создания URL-адресов «ленивым» способом (вычисляется при обращении)
from django.urls import reverse_lazy
# Получение объекта или автоматический возврат 404 при его отсутствии
from django.shortcuts import get_object_or_404
# Q-объект для построения сложных запросов с логическими операторами
from django.db.models import Q
# Стандартная библиотека для работы с JSON
import json

# Модель сотрудника — нужна для получения роли и настроек пользователя
from apps.employees.models import Employee
# Модель отдела — используется в контексте для фильтрации по отделам
from apps.employees.models import Department
# Основные модели данного приложения
from .models import Work, WorkReport, Notice
# Формы для создания и редактирования объектов
from .forms  import WorkForm, WorkReportForm, NoticeForm
# Стандартная библиотека для работы с датами
import datetime


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
        # Получаем профиль Employee для данного пользователя
        emp = user.employee
    except Employee.DoesNotExist:
        # Если профиля нет — суперпользователь видит всё, остальные — ничего
        if user.is_superuser:
            return Q()
        return Q(pk__in=[])   # ничего не показываем

    # Получаем роль сотрудника для дальнейшей логики
    role = emp.role

    # Администратор и суперпользователь видят все записи без ограничений
    if role == Employee.ROLE_ADMIN or user.is_superuser:
        return Q()

    # Руководители НТЦ видят все работы своего НТЦ-центра
    if role in (Employee.ROLE_NTC_HEAD, Employee.ROLE_NTC_DEPUTY):
        return Q(ntc_center=emp.ntc_center)

    # Начальники и замы отдела видят все работы своего отдела
    if role in (Employee.ROLE_DEPT_HEAD, Employee.ROLE_DEPT_DEPUTY):
        return Q(department=emp.department)

    # Начальник сектора видит работы своего отдела И своего сектора
    if role == Employee.ROLE_SECTOR_HEAD:
        return Q(department=emp.department, sector=emp.sector)

    # ROLE_USER — только свои работы (исполнитель или создатель)
    return Q(executor=emp) | Q(created_by=emp)


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
        ).filter(visibility_filter(self.request.user))

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
        # Передаём в шаблон список вариантов источника (для фильтров)
        ctx['source_choices'] = Work.SOURCE_CHOICES
        # Список всех отделов (для фильтра по отделу)
        ctx['departments'] = Department.objects.order_by('code')
        # Диапазон годов для фильтра (3 прошлых + текущий + 2 будущих)
        current_year = datetime.date.today().year
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
            visibility_filter(self.request.user)
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
        return Work.objects.filter(visibility_filter(self.request.user))

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
        return Work.objects.filter(visibility_filter(self.request.user))


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

class NoticeListView(LoginRequiredMixin, ListView):
    # Модель журнала извещений
    model               = Notice
    # Шаблон списка извещений
    template_name       = 'works/notice_list.html'
    # Имя переменной в контексте шаблона
    context_object_name = 'notices'
    # Количество записей на странице
    paginate_by         = 30

    def get_queryset(self):
        # Загружаем извещения с JOIN'ами по отделу и исполнителю
        qs = Notice.objects.select_related('department', 'executor')
        # Фильтр по статусу (активные / закрытые)
        status = self.request.GET.get('status')
        if status in (Notice.STATUS_ACTIVE, Notice.STATUS_CLOSED):
            qs = qs.filter(status=status)
        # Сортировка: самые свежие извещения первыми
        return qs.order_by('-date_issued')


class NoticeDetailView(LoginRequiredMixin, DetailView):
    # Детальная страница одного извещения
    model         = Notice
    template_name = 'works/notice_detail.html'


class NoticeCreateView(WriterRequiredMixin, CreateView):
    # Форма создания нового извещения
    model         = Notice
    form_class    = NoticeForm
    template_name = 'works/notice_form.html'
    # После создания перенаправляем на список извещений
    success_url   = reverse_lazy('works:notice_list')


class NoticeUpdateView(WriterRequiredMixin, UpdateView):
    # Форма редактирования извещения
    model         = Notice
    form_class    = NoticeForm
    template_name = 'works/notice_form.html'
    # После сохранения возвращаем на список извещений
    success_url   = reverse_lazy('works:notice_list')


# ── План/Отчёт SPA ──────────────────────────────────────────────────────────

class PlanSPAView(LoginRequiredMixin, TemplateView):
    """Главная SPA-страница «План/Отчёт» — аналог Flask plan.html."""
    # Шаблон SPA с подключением JS-логики
    template_name = 'works/plan_spa.html'

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Пытаемся получить профиль Employee для данного пользователя
        emp = getattr(self.request.user, 'employee', None)
        # Роль: из профиля Employee или дефолтная ('admin' для суперпользователя)
        ctx['role'] = emp.role if emp else ('admin' if self.request.user.is_superuser else 'user')
        # Отображаемое имя: краткое ФИО или username
        ctx['username'] = emp.short_name if emp else self.request.user.username
        # Флаг права записи: для JS-логики отключения/включения кнопок редактирования
        ctx['is_writer'] = (emp.is_writer if emp else self.request.user.is_superuser)
        # Настройки ширин колонок
        col_settings = {}
        if emp and emp.col_settings:
            # Убеждаемся, что col_settings — словарь (не строка, не None)
            col_settings = emp.col_settings if isinstance(emp.col_settings, dict) else {}
        # Сериализуем в JSON для передачи в JS через data-атрибут или глобальную переменную
        ctx['col_settings'] = json.dumps(col_settings)
        return ctx


class ProjectsSPAView(LoginRequiredMixin, TemplateView):
    """SPA-страница «Управление проектами»."""
    # Шаблон SPA-модуля управления проектами (УП)
    template_name = 'works/projects_spa.html'

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Пытаемся получить профиль Employee
        emp = getattr(self.request.user, 'employee', None)
        # Роль и имя аналогично PlanSPAView
        ctx['role'] = emp.role if emp else ('admin' if self.request.user.is_superuser else 'user')
        ctx['username'] = emp.short_name if emp else self.request.user.username
        # Флаг права записи для JS
        ctx['is_writer'] = (emp.is_writer if emp else self.request.user.is_superuser)
        return ctx


class ProductionPlanSPAView(LoginRequiredMixin, TemplateView):
    """SPA-страница «Производственный план»."""
    # Шаблон SPA-модуля производственного плана (ПП)
    template_name = 'works/production_plan_spa.html'

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Пытаемся получить профиль Employee
        emp = getattr(self.request.user, 'employee', None)
        # Роль, имя и права записи — стандартный набор для SPA-страниц
        ctx['role'] = emp.role if emp else ('admin' if self.request.user.is_superuser else 'user')
        ctx['username'] = emp.short_name if emp else self.request.user.username
        ctx['is_writer'] = (emp.is_writer if emp else self.request.user.is_superuser)
        return ctx


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    # Разрешает доступ только администраторам (роль 'admin') и суперпользователям
    def test_func(self):
        try:
            # Проверяем роль сотрудника
            return self.request.user.employee.role == 'admin'
        except Exception:
            # При любой ошибке (нет профиля и т.д.) — проверяем is_superuser
            return self.request.user.is_superuser


class WorkCalendarSPAView(AdminRequiredMixin, TemplateView):
    """SPA-страница «Производственный календарь» — только для администратора."""
    # Шаблон SPA-модуля управления производственным календарём
    template_name = 'works/work_calendar_spa.html'

    def get_context_data(self, **kwargs):
        # Получаем базовый контекст
        ctx = super().get_context_data(**kwargs)
        # Пытаемся получить профиль Employee
        emp = getattr(self.request.user, 'employee', None)
        # Отображаемое имя пользователя
        ctx['username'] = emp.short_name if emp else self.request.user.username
        # Текущий год — используется для инициализации выбора года в интерфейсе
        current_year = datetime.date.today().year
        ctx['current_year'] = current_year
        # Диапазон годов для переключателя (3 прошлых + текущий + 3 будущих)
        ctx['years'] = list(range(current_year - 3, current_year + 4))
        return ctx
