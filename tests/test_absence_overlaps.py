"""
Тесты API /api/absence_overlaps/ — проверка пересечений отсутствий.
"""
import json
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.employees.models import BusinessTrip, Department, Employee, Vacation

User = get_user_model()


@pytest.fixture
def dept_ov(db):
    return Department.objects.create(code='022', name='Отдел 22')


def _make_emp(dept, last, first, pat, role='user'):
    u = User.objects.create_user(username=last.lower() + '_ov', password='pass123')
    return Employee.objects.create(
        user=u, last_name=last, first_name=first, patronymic=pat,
        role=role, department=dept,
    )


@pytest.fixture
def emp_a(dept_ov):
    return _make_emp(dept_ov, 'Иванов', 'Иван', 'Иванович')


@pytest.fixture
def emp_b(dept_ov):
    return _make_emp(dept_ov, 'Петров', 'Пётр', 'Петрович')


@pytest.fixture
def emp_c(dept_ov):
    return _make_emp(dept_ov, 'Сидоров', 'Сидор', 'Сидорович')


@pytest.fixture
def admin_ov(dept_ov):
    return _make_emp(dept_ov, 'АдминОВ', 'Тест', 'Тестович', role='admin')


def _post(client, data):
    return client.post(
        '/api/absence_overlaps/',
        json.dumps(data),
        content_type='application/json',
    )


class TestAbsenceOverlaps:
    def test_401_unauthenticated(self, db):
        c = Client()
        r = _post(c, {'employee_ids': [1, 2]})
        assert r.status_code == 401

    def test_400_less_than_2(self, admin_ov):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        r = _post(c, {'employee_ids': [1]})
        assert r.status_code == 400

    def test_400_empty(self, admin_ov):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        r = _post(c, {'employee_ids': []})
        assert r.status_code == 400

    def test_no_overlaps(self, admin_ov, emp_a, emp_b):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        Vacation.objects.create(
            employee=emp_a, date_start=date(2026, 3, 1), date_end=date(2026, 3, 10))
        Vacation.objects.create(
            employee=emp_b, date_start=date(2026, 3, 15), date_end=date(2026, 3, 25))
        r = _post(c, {'employee_ids': [emp_a.pk, emp_b.pk]})
        assert r.status_code == 200
        assert r.json()['summary']['total_overlaps'] == 0

    def test_vacation_vacation_overlap(self, admin_ov, emp_a, emp_b):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        Vacation.objects.create(
            employee=emp_a, date_start=date(2026, 3, 1), date_end=date(2026, 3, 15))
        Vacation.objects.create(
            employee=emp_b, date_start=date(2026, 3, 10), date_end=date(2026, 3, 25))
        r = _post(c, {'employee_ids': [emp_a.pk, emp_b.pk]})
        data = r.json()
        assert data['summary']['total_overlaps'] == 1
        ov = data['overlaps'][0]
        assert ov['overlap_start'] == '2026-03-10'
        assert ov['overlap_end'] == '2026-03-15'
        assert ov['duration_days'] == 6
        assert len(ov['employees']) == 2

    def test_vacation_trip_overlap(self, admin_ov, emp_a, emp_b):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        Vacation.objects.create(
            employee=emp_a, date_start=date(2026, 6, 1), date_end=date(2026, 6, 15))
        BusinessTrip.objects.create(
            employee=emp_b, date_start=date(2026, 6, 10), date_end=date(2026, 6, 20),
            location='Москва', status='plan')
        r = _post(c, {
            'employee_ids': [emp_a.pk, emp_b.pk],
            'include_vacations': True, 'include_trips': True,
        })
        data = r.json()
        assert data['summary']['total_overlaps'] == 1
        types = {e['type'] for e in data['overlaps'][0]['employees']}
        assert types == {'vacation', 'trip'}

    def test_trip_trip_overlap(self, admin_ov, emp_a, emp_b):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        BusinessTrip.objects.create(
            employee=emp_a, date_start=date(2026, 4, 1), date_end=date(2026, 4, 10),
            location='СПб', status='plan')
        BusinessTrip.objects.create(
            employee=emp_b, date_start=date(2026, 4, 5), date_end=date(2026, 4, 15),
            location='Москва', status='plan')
        r = _post(c, {
            'employee_ids': [emp_a.pk, emp_b.pk],
            'include_vacations': False, 'include_trips': True,
        })
        data = r.json()
        assert data['summary']['total_overlaps'] == 1
        assert data['overlaps'][0]['overlap_start'] == '2026-04-05'
        assert data['overlaps'][0]['overlap_end'] == '2026-04-10'

    def test_include_vacations_false(self, admin_ov, emp_a, emp_b):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        Vacation.objects.create(
            employee=emp_a, date_start=date(2026, 5, 1), date_end=date(2026, 5, 15))
        Vacation.objects.create(
            employee=emp_b, date_start=date(2026, 5, 10), date_end=date(2026, 5, 25))
        r = _post(c, {
            'employee_ids': [emp_a.pk, emp_b.pk],
            'include_vacations': False, 'include_trips': True,
        })
        assert r.json()['summary']['total_overlaps'] == 0

    def test_include_trips_false(self, admin_ov, emp_a, emp_b):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        BusinessTrip.objects.create(
            employee=emp_a, date_start=date(2026, 7, 1), date_end=date(2026, 7, 10),
            location='Казань', status='active')
        BusinessTrip.objects.create(
            employee=emp_b, date_start=date(2026, 7, 5), date_end=date(2026, 7, 15),
            location='Самара', status='plan')
        r = _post(c, {
            'employee_ids': [emp_a.pk, emp_b.pk],
            'include_vacations': True, 'include_trips': False,
        })
        assert r.json()['summary']['total_overlaps'] == 0

    def test_date_range_filter(self, admin_ov, emp_a, emp_b):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        Vacation.objects.create(
            employee=emp_a, date_start=date(2026, 1, 1), date_end=date(2026, 1, 15))
        Vacation.objects.create(
            employee=emp_b, date_start=date(2026, 1, 10), date_end=date(2026, 1, 25))
        r = _post(c, {
            'employee_ids': [emp_a.pk, emp_b.pk],
            'date_from': '2026-02-01', 'date_to': '2026-12-31',
        })
        assert r.json()['summary']['total_overlaps'] == 0

    def test_same_employee_ignored(self, admin_ov, emp_a, emp_b):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        Vacation.objects.create(
            employee=emp_a, date_start=date(2026, 8, 1), date_end=date(2026, 8, 15))
        BusinessTrip.objects.create(
            employee=emp_a, date_start=date(2026, 8, 10), date_end=date(2026, 8, 20),
            location='Тула', status='plan')
        r = _post(c, {'employee_ids': [emp_a.pk, emp_b.pk]})
        assert r.json()['summary']['total_overlaps'] == 0

    def test_cancelled_trips_excluded(self, admin_ov, emp_a, emp_b):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        BusinessTrip.objects.create(
            employee=emp_a, date_start=date(2026, 9, 1), date_end=date(2026, 9, 10),
            location='Москва', status='cancel')
        BusinessTrip.objects.create(
            employee=emp_b, date_start=date(2026, 9, 5), date_end=date(2026, 9, 15),
            location='СПб', status='plan')
        r = _post(c, {
            'employee_ids': [emp_a.pk, emp_b.pk],
            'include_vacations': False, 'include_trips': True,
        })
        assert r.json()['summary']['total_overlaps'] == 0

    def test_timeline_returned(self, admin_ov, emp_a, emp_b):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        Vacation.objects.create(
            employee=emp_a, date_start=date(2026, 3, 1), date_end=date(2026, 3, 15))
        Vacation.objects.create(
            employee=emp_b, date_start=date(2026, 3, 10), date_end=date(2026, 3, 25))
        r = _post(c, {'employee_ids': [emp_a.pk, emp_b.pk]})
        data = r.json()
        assert 'timeline' in data
        assert len(data['timeline']) == 2
        for tl in data['timeline']:
            assert len(tl['periods']) > 0

    def test_three_employees_overlap(self, admin_ov, emp_a, emp_b, emp_c):
        c = Client()
        c.login(username='админов_ov', password='pass123')
        Vacation.objects.create(
            employee=emp_a, date_start=date(2026, 5, 1), date_end=date(2026, 5, 20))
        Vacation.objects.create(
            employee=emp_b, date_start=date(2026, 5, 10), date_end=date(2026, 5, 25))
        Vacation.objects.create(
            employee=emp_c, date_start=date(2026, 5, 15), date_end=date(2026, 5, 30))
        r = _post(c, {'employee_ids': [emp_a.pk, emp_b.pk, emp_c.pk]})
        data = r.json()
        assert data['summary']['total_overlaps'] >= 2
        assert data['summary']['employees_involved'] == 3
