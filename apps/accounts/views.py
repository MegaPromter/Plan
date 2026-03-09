from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.views.generic import FormView, TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Count


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
        from apps.works.models import Work, Notice
        from apps.employees.models import Employee, Vacation
        ctx = super().get_context_data(**kwargs)
        ctx['works_count']    = Work.objects.count()
        ctx['tasks_count']    = Work.objects.filter(show_in_plan=True).count()
        ctx['pp_count']       = Work.objects.filter(show_in_pp=True).count()
        ctx['notices_count']  = Notice.objects.count()
        ctx['employees_count']= Employee.objects.filter(is_active=True).count()
        ctx['vacations_count']= Vacation.objects.count()
        return ctx


# Заглушка для разделов в разработке
_STUB_TITLES = {
    'projects-list':         ('Проекты',                   'Список проектов и их основных характеристик'),
    'projects-stages':       ('Этапы и вехи',               'Управление иерархией этапов проектов'),
    'projects-deadlines':    ('Сроки и вехи',              'Контрольные точки и плановые сроки по проектам'),
    'pp-import':             ('Импорт / экспорт ПП',       'Загрузка и выгрузка данных производственного плана'),
    'analytics-workload':    ('Загрузка сотрудников',      'Анализ плановой и фактической нагрузки по исполнителям'),
    'analytics-deadlines':   ('Исполнение сроков',         'Статистика соблюдения плановых дат завершения работ'),
    'analytics-reports':     ('Отчёты',                    'Сводные аналитические отчёты по планированию и отчётности'),
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


class AdminSPAView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/admin_spa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = getattr(self.request.user, 'employee', None)
        ctx['role']       = emp.role if emp else ('admin' if self.request.user.is_superuser else 'user')
        ctx['username']   = emp.short_name if emp else self.request.user.username
        ctx['is_writer']  = (emp.is_writer if emp else self.request.user.is_superuser)
        return ctx
