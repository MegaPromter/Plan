from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.views.generic import FormView, TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Count
from django.db.models.functions import Coalesce


class ChangePasswordView(LoginRequiredMixin, FormView):
    template_name = 'accounts/change_password.html'
    form_class    = PasswordChangeForm
    success_url   = reverse_lazy('accounts:profile')

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['user'] = self.request.user
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx['forced'] = self.request.user.employee.must_change_password
        except Exception:
            ctx['forced'] = False
        return ctx

    def form_valid(self, form):
        form.save()
        update_session_auth_hash(self.request, form.user)
        # Снять флаг принудительной смены, если есть профиль
        try:
            emp = self.request.user.employee
            emp.must_change_password = False
            emp.save(update_fields=['must_change_password'])
        except Exception:
            pass
        messages.success(self.request, 'Пароль успешно изменён.')
        return super().form_valid(form)


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx['employee'] = self.request.user.employee
        except Exception:
            ctx['employee'] = None
        return ctx


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/dashboard.html'

    def get_context_data(self, **kwargs):
        from datetime import timedelta
        from django.db.models import Exists, OuterRef, Q
        from django.utils import timezone
        from apps.works.models import Work, Notice, WorkReport
        from apps.employees.models import Employee, Vacation
        from apps.api.utils import get_visibility_filter
        ctx = super().get_context_data(**kwargs)
        vis_q = get_visibility_filter(self.request.user)
        ctx['works_count']    = Work.objects.filter(vis_q).count()
        ctx['tasks_count']    = Work.objects.filter(show_in_plan=True).filter(vis_q).count()
        ctx['pp_count']       = Work.objects.filter(show_in_pp=True).count()
        ctx['notices_count']  = Notice.objects.count()
        ctx['employees_count']= Employee.objects.filter(is_active=True).count()
        ctx['vacations_count']= Vacation.objects.count()

        # Персональная статистика для hero-секции
        today = timezone.now().date()
        emp = getattr(self.request.user, 'employee', None)
        if emp:
            has_reports = Exists(WorkReport.objects.filter(work=OuterRef('pk')))
            my_tasks = Work.objects.filter(
                show_in_plan=True, executor=emp
            ).annotate(
                _done=has_reports,
                _eff_deadline=Coalesce('deadline', 'date_end'),
            )
            my_overdue = my_tasks.filter(_done=False, _eff_deadline__lt=today).count()
            my_upcoming = my_tasks.filter(
                _done=False,
                _eff_deadline__gte=today,
                _eff_deadline__lte=today + timedelta(days=7),
            ).count()
            ctx['my_overdue'] = my_overdue
            ctx['my_upcoming'] = my_upcoming
        else:
            ctx['my_overdue'] = 0
            ctx['my_upcoming'] = 0

        # Имя Отчество для приветствия (fallback на username)
        display_name = ''
        if emp:
            parts = [p for p in (emp.first_name, emp.patronymic) if p]
            display_name = ' '.join(parts)
        if not display_name:
            display_name = (self.request.user.first_name or '').strip()
        if not display_name:
            display_name = self.request.user.username
        ctx['display_name'] = display_name
        return ctx


# Заглушка для разделов в разработке
_STUB_TITLES = {
    'projects-list':         ('Проекты',                   'Список проектов и их основных характеристик'),
    'projects-stages':       ('Этапы и вехи',               'Управление иерархией этапов проектов'),
    'projects-deadlines':    ('Сроки и вехи',              'Контрольные точки и плановые сроки по проектам'),
    'pp-import':             ('Импорт / экспорт ПП',       'Загрузка и выгрузка данных производственного плана'),
    'analytics-workload':    ('Доска руководителя',         'Аналитика: загрузка, дедлайны, выполнение плана'),
    'analytics-employee':    ('Доска сотрудника',          'Персональные задачи и загрузка по часам'),
    'analytics-pp':          ('Отчёты ПП',                 'Метрики производственного плана: трудоёмкость, листы, типы работ'),
}

class StubView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/stub.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug = kwargs.get('slug', '')
        title, desc = _STUB_TITLES.get(slug, ('Раздел в разработке', 'Функциональность находится в разработке'))
        ctx['stub_title'] = title
        ctx['stub_desc']  = desc
        return ctx


class AdminSPAView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'accounts/admin_spa.html'

    def test_func(self):
        try:
            return self.request.user.employee.role == 'admin'
        except Exception:
            return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = getattr(self.request.user, 'employee', None)
        ctx['role']       = emp.role if emp else ('admin' if self.request.user.is_superuser else 'user')
        ctx['username']   = emp.short_name if emp else self.request.user.username
        ctx['is_writer']  = (emp.is_writer if emp else self.request.user.is_superuser)
        return ctx
