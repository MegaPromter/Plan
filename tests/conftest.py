"""
Общие фикстуры для тестов.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.employees.models import Employee, Department, NTCCenter, Sector

User = get_user_model()


@pytest.fixture
def dept(db):
    return Department.objects.create(code='101', name='Тестовый отдел')


@pytest.fixture
def sector(db, dept):
    return Sector.objects.create(department=dept, code='101-1', name='Тестовый сектор')


@pytest.fixture
def ntc(db):
    return NTCCenter.objects.create(code='НТЦ-1Ц', name='Тест НТЦ')


@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(username='admin_test', password='testpass123')
    emp = Employee.objects.create(
        user=user,
        last_name='Иванов',
        first_name='Иван',
        patronymic='Иванович',
        role=Employee.ROLE_ADMIN,
    )
    return user


@pytest.fixture
def regular_user(db, dept):
    user = User.objects.create_user(username='user_test', password='testpass123')
    emp = Employee.objects.create(
        user=user,
        last_name='Петров',
        first_name='Пётр',
        patronymic='Петрович',
        role=Employee.ROLE_USER,
        department=dept,
    )
    return user


@pytest.fixture
def dept_head_user(db, dept):
    user = User.objects.create_user(username='dept_head_test', password='testpass123')
    emp = Employee.objects.create(
        user=user,
        last_name='Сидоров',
        first_name='Сидор',
        patronymic='Сидорович',
        role=Employee.ROLE_DEPT_HEAD,
        department=dept,
    )
    return user
