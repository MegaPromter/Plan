"""
Тесты WorkCalendar API.
"""
import json

import pytest
from django.test import Client

from apps.works.models import WorkCalendar


@pytest.mark.django_db
class TestWorkCalendarList:
    def test_requires_auth(self):
        resp = Client().get('/api/work_calendar/')
        assert resp.status_code == 401

    def test_list_all(self, admin_user):
        WorkCalendar.objects.create(year=2026, month=1, hours_norm=136)
        WorkCalendar.objects.create(year=2026, month=2, hours_norm=152)
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/work_calendar/')
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_year(self, admin_user):
        WorkCalendar.objects.create(year=2026, month=3, hours_norm=168)
        WorkCalendar.objects.create(year=2027, month=3, hours_norm=176)
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/work_calendar/?year=2026')
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_regular_user_can_list(self, regular_user):
        WorkCalendar.objects.create(year=2026, month=4, hours_norm=168)
        c = Client()
        c.force_login(regular_user)
        resp = c.get('/api/work_calendar/')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestWorkCalendarCreate:
    def test_create_new(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.post('/api/work_calendar/create/',
            json.dumps({'year': 2026, 'month': 5, 'hours_norm': 152}),
            content_type='application/json')
        assert resp.status_code == 201
        assert WorkCalendar.objects.filter(year=2026, month=5).exists()

    def test_upsert_existing(self, admin_user):
        WorkCalendar.objects.create(year=2026, month=6, hours_norm=100)
        c = Client()
        c.force_login(admin_user)
        resp = c.post('/api/work_calendar/create/',
            json.dumps({'year': 2026, 'month': 6, 'hours_norm': 168}),
            content_type='application/json')
        assert resp.status_code == 200
        cal = WorkCalendar.objects.get(year=2026, month=6)
        assert float(cal.hours_norm) == 168.0

    def test_invalid_month_400(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.post('/api/work_calendar/create/',
            json.dumps({'year': 2026, 'month': 13, 'hours_norm': 100}),
            content_type='application/json')
        assert resp.status_code == 400

    def test_negative_hours_400(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.post('/api/work_calendar/create/',
            json.dumps({'year': 2026, 'month': 7, 'hours_norm': -10}),
            content_type='application/json')
        assert resp.status_code == 400

    def test_requires_admin(self, regular_user):
        c = Client()
        c.force_login(regular_user)
        resp = c.post('/api/work_calendar/create/',
            json.dumps({'year': 2026, 'month': 8, 'hours_norm': 160}),
            content_type='application/json')
        assert resp.status_code == 403


@pytest.mark.django_db
class TestWorkCalendarDetail:
    def test_update_hours(self, admin_user):
        cal = WorkCalendar.objects.create(year=2026, month=9, hours_norm=168)
        c = Client()
        c.force_login(admin_user)
        resp = c.put(f'/api/work_calendar/{cal.id}/',
            json.dumps({'hours_norm': 176}),
            content_type='application/json')
        assert resp.status_code == 200
        cal.refresh_from_db()
        assert float(cal.hours_norm) == 176.0

    def test_delete(self, admin_user):
        cal = WorkCalendar.objects.create(year=2026, month=10, hours_norm=184)
        c = Client()
        c.force_login(admin_user)
        resp = c.delete(f'/api/work_calendar/{cal.id}/')
        assert resp.status_code == 200
        assert not WorkCalendar.objects.filter(id=cal.id).exists()

    def test_not_found_404(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.put('/api/work_calendar/99999/',
            json.dumps({'hours_norm': 100}),
            content_type='application/json')
        assert resp.status_code == 404
