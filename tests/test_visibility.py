"""
Тесты фильтрации видимости данных по ролям.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.api.utils import get_visibility_filter

User = get_user_model()


@pytest.mark.django_db
class TestVisibilityFilter:
    def test_admin_sees_all(self, admin_user):
        q = get_visibility_filter(admin_user)
        # Q() без условий — пустой фильтр (видит всё)
        assert str(q) == str(type(q)())

    def test_no_employee_sees_nothing(self, db):
        user = User.objects.create_user(username='noemployee', password='pass123')
        q = get_visibility_filter(user)
        assert 'isnull' in str(q).lower() or 'pk' in str(q).lower()

    def test_user_sees_own_tasks(self, regular_user):
        emp = regular_user.employee
        q = get_visibility_filter(regular_user)
        q_str = str(q)
        # Пользователь с отделом видит задачи отдела; без отдела — свои (executor/created_by)
        assert 'department' in q_str.lower() or 'executor' in q_str.lower() or str(emp.pk) in q_str

    def test_dept_head_sees_dept(self, dept_head_user, dept):
        q = get_visibility_filter(dept_head_user)
        q_str = str(q)
        assert 'department' in q_str.lower()


@pytest.mark.django_db
class TestVacationVisibilityFilter:
    from apps.api.utils import get_vacation_visibility_filter

    def test_admin_vacation_sees_all(self, admin_user):
        from apps.api.utils import get_vacation_visibility_filter
        q = get_vacation_visibility_filter(admin_user)
        assert str(q) == str(type(q)())

    def test_user_sees_own_vacation(self, regular_user):
        from apps.api.utils import get_vacation_visibility_filter
        q = get_vacation_visibility_filter(regular_user)
        q_str = str(q)
        assert 'employee' in q_str.lower()
