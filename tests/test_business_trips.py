"""
Тесты BusinessTrip API (План командировок).
"""
import json
from datetime import date

import pytest
from django.test import Client

from apps.employees.models import BusinessTrip, Employee


@pytest.fixture
def employee(db, dept):
    """Сотрудник для привязки командировок."""
    user = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
    u = user.objects.create_user(username='trip_emp', password='testpass123')
    return Employee.objects.create(
        user=u,
        last_name='Козлов',
        first_name='Дмитрий',
        patronymic='Евгеньевич',
        role=Employee.ROLE_USER,
        department=dept,
    )


@pytest.fixture
def trip(db, employee):
    """Одна командировка."""
    return BusinessTrip.objects.create(
        employee=employee,
        location='СПб, Северная верфь',
        purpose='Авторский надзор',
        date_start=date(2026, 3, 12),
        date_end=date(2026, 3, 16),
        status=BusinessTrip.STATUS_PLAN,
    )


# ── GET /api/business_trips/ ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestBusinessTripList:
    def test_requires_auth(self):
        resp = Client().get('/api/business_trips/')
        assert resp.status_code == 401

    def test_list_returns_data(self, admin_user, trip):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/business_trips/')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]['location'] == 'СПб, Северная верфь'
        assert data[0]['duration_days'] == 5

    def test_filter_by_year(self, admin_user, trip):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/business_trips/?year=2026')
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        resp2 = c.get('/api/business_trips/?year=2025')
        assert len(resp2.json()) == 0

    def test_filter_by_status(self, admin_user, trip):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/business_trips/?status=plan')
        assert resp.status_code == 200
        assert all(t['status'] == 'plan' for t in resp.json())
        resp2 = c.get('/api/business_trips/?status=done')
        assert len(resp2.json()) == 0

    def test_filter_by_executor(self, admin_user, trip):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/business_trips/?executor=Козлов')
        assert len(resp.json()) == 1
        resp2 = c.get('/api/business_trips/?executor=Несуществующий')
        assert len(resp2.json()) == 0


# ── POST /api/business_trips/ ────────────────────────────────────────────────

@pytest.mark.django_db
class TestBusinessTripCreate:
    def test_create_requires_writer(self, regular_user, employee):
        c = Client()
        c.force_login(regular_user)
        resp = c.post(
            '/api/business_trips/',
            data=json.dumps({
                'employee_id': employee.pk,
                'location': 'Москва',
                'date_start': '2026-04-01',
                'date_end': '2026-04-03',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_create_by_admin(self, admin_user, employee):
        c = Client()
        c.force_login(admin_user)
        resp = c.post(
            '/api/business_trips/',
            data=json.dumps({
                'employee_id': employee.pk,
                'location': 'Калининград, ПСЗ Янтарь',
                'purpose': 'Шеф-монтаж',
                'date_start': '2026-04-07',
                'date_end': '2026-04-18',
                'status': 'plan',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['location'] == 'Калининград, ПСЗ Янтарь'
        assert data['duration_days'] == 12
        assert data['executor'] == 'Козлов Дмитрий Евгеньевич'

    def test_create_by_executor_name(self, admin_user, employee):
        c = Client()
        c.force_login(admin_user)
        resp = c.post(
            '/api/business_trips/',
            data=json.dumps({
                'executor': 'Козлов Дмитрий Евгеньевич',
                'location': 'Астрахань',
                'date_start': '2026-05-10',
                'date_end': '2026-05-14',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        assert resp.json()['employee_id'] == employee.pk

    def test_create_validates_dates(self, admin_user, employee):
        c = Client()
        c.force_login(admin_user)
        resp = c.post(
            '/api/business_trips/',
            data=json.dumps({
                'employee_id': employee.pk,
                'location': 'Москва',
                'date_start': '2026-04-10',
                'date_end': '2026-04-05',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert 'раньше' in resp.json()['error']

    def test_create_requires_location(self, admin_user, employee):
        c = Client()
        c.force_login(admin_user)
        resp = c.post(
            '/api/business_trips/',
            data=json.dumps({
                'employee_id': employee.pk,
                'location': '',
                'date_start': '2026-04-01',
                'date_end': '2026-04-03',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400


# ── PUT /api/business_trips/<id>/ ────────────────────────────────────────────

@pytest.mark.django_db
class TestBusinessTripUpdate:
    def test_update_requires_writer(self, regular_user, trip):
        c = Client()
        c.force_login(regular_user)
        resp = c.put(
            f'/api/business_trips/{trip.pk}/',
            data=json.dumps({'status': 'done'}),
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_update_by_admin(self, admin_user, trip):
        c = Client()
        c.force_login(admin_user)
        resp = c.put(
            f'/api/business_trips/{trip.pk}/',
            data=json.dumps({'status': 'done', 'location': 'Москва, ЦНИИ'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'done'
        assert data['location'] == 'Москва, ЦНИИ'

    def test_update_404(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.put(
            '/api/business_trips/99999/',
            data=json.dumps({'status': 'done'}),
            content_type='application/json',
        )
        assert resp.status_code == 404


# ── DELETE /api/business_trips/<id>/ ─────────────────────────────────────────

@pytest.mark.django_db
class TestBusinessTripDelete:
    def test_delete_requires_writer(self, regular_user, trip):
        c = Client()
        c.force_login(regular_user)
        resp = c.delete(f'/api/business_trips/{trip.pk}/')
        assert resp.status_code == 403

    def test_delete_by_admin(self, admin_user, trip):
        c = Client()
        c.force_login(admin_user)
        resp = c.delete(f'/api/business_trips/{trip.pk}/')
        assert resp.status_code == 200
        assert not BusinessTrip.objects.filter(pk=trip.pk).exists()

    def test_delete_404(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.delete('/api/business_trips/99999/')
        assert resp.status_code == 404


# ── Model ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBusinessTripModel:
    def test_duration_days(self, trip):
        assert trip.duration_days == 5

    def test_str(self, trip):
        assert str(trip.date_start) == '2026-03-12'
