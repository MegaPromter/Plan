from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView


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
        from django.utils import timezone
        ctx = super().get_context_data(**kwargs)

        today = timezone.now().date()
        emp = getattr(self.request.user, 'employee', None)

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

        # Контекст для JS-конфига
        ctx['current_year'] = today.year
        ctx['current_month'] = today.month
        ctx['role'] = emp.role if emp else 'user'
        ctx['is_writer'] = emp.is_writer if emp else False

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
