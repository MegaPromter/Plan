"""
Тесты Holiday API и _add_work_days() с учётом праздников.
"""
import json
from datetime import date

import pytest
from django.test import Client

from apps.api.views.dependencies import (
    _add_work_days,
    invalidate_holiday_cache,
)
from apps.works.models import Holiday


# ── _add_work_days() с праздниками ──────────────────────────────────────────


@pytest.mark.django_db
class TestAddWorkDaysWithHolidays:
    def setup_method(self):
        invalidate_holiday_cache()

    def teardown_method(self):
        invalidate_holiday_cache()

    def test_skips_weekends(self):
        # Пятница 2026-03-13 + 1 рабочий день = Понедельник 2026-03-16
        result = _add_work_days(date(2026, 3, 13), 1)
        assert result == date(2026, 3, 16)

    def test_skips_holiday_on_weekday(self):
        # Создаём праздник на понедельник
        Holiday.objects.create(date=date(2026, 3, 16), name='Тестовый праздник')
        invalidate_holiday_cache()
        # Пятница + 1 = должен пропустить пн-праздник → вторник
        result = _add_work_days(date(2026, 3, 13), 1)
        assert result == date(2026, 3, 17)

    def test_skips_consecutive_holidays(self):
        Holiday.objects.create(date=date(2026, 3, 16), name='Праздник 1')
        Holiday.objects.create(date=date(2026, 3, 17), name='Праздник 2')
        invalidate_holiday_cache()
        # Пятница + 1 = пропускает сб, вс, пн-праздник, вт-праздник → среда
        result = _add_work_days(date(2026, 3, 13), 1)
        assert result == date(2026, 3, 18)

    def test_backward_skips_holiday(self):
        Holiday.objects.create(date=date(2026, 3, 13), name='Праздник')
        invalidate_holiday_cache()
        # Понедельник 2026-03-16 - 1 = пропускает сб, вс, пт-праздник → четверг
        result = _add_work_days(date(2026, 3, 16), -1)
        assert result == date(2026, 3, 12)

    def test_zero_days_returns_same(self):
        result = _add_work_days(date(2026, 3, 13), 0)
        assert result == date(2026, 3, 13)

    def test_no_holidays_weekday_only(self):
        # Понедельник + 5 = следующий понедельник
        result = _add_work_days(date(2026, 3, 16), 5)
        assert result == date(2026, 3, 23)

    def test_weekend_holiday_doesnt_double_count(self):
        # Праздник на субботу — не должен влиять (суббота и так выходной)
        Holiday.objects.create(date=date(2026, 3, 14), name='Субботний праздник')
        invalidate_holiday_cache()
        result = _add_work_days(date(2026, 3, 13), 1)
        # Пятница + 1 = Понедельник (суббота-праздник не влияет)
        assert result == date(2026, 3, 16)


# ── Holiday API ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestHolidayAPI:
    def test_list_empty(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        resp = client.get('/api/holidays/')
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_holiday(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            '/api/holidays/',
            json.dumps({'date': '2026-06-12', 'name': 'День России'}),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['date'] == '2026-06-12'
        assert data['name'] == 'День России'
        assert Holiday.objects.count() == 1

    def test_create_duplicate_409(self, admin_user):
        Holiday.objects.create(date=date(2026, 6, 12), name='День России')
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            '/api/holidays/',
            json.dumps({'date': '2026-06-12', 'name': 'Дубль'}),
            content_type='application/json',
        )
        assert resp.status_code == 409

    def test_create_bad_date_400(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            '/api/holidays/',
            json.dumps({'date': 'not-a-date'}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_delete_holiday(self, admin_user):
        h = Holiday.objects.create(date=date(2026, 11, 4), name='День единства')
        client = Client()
        client.force_login(admin_user)
        resp = client.delete(f'/api/holidays/{h.id}/')
        assert resp.status_code == 200
        assert Holiday.objects.count() == 0

    def test_delete_not_found_404(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        resp = client.delete('/api/holidays/99999/')
        assert resp.status_code == 404

    def test_list_filter_by_year(self, admin_user):
        Holiday.objects.create(date=date(2026, 1, 1), name='НГ 2026')
        Holiday.objects.create(date=date(2027, 1, 1), name='НГ 2027')
        client = Client()
        client.force_login(admin_user)
        resp = client.get('/api/holidays/?year=2026')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['date'] == '2026-01-01'

    def test_regular_user_can_list(self, regular_user):
        Holiday.objects.create(date=date(2026, 5, 1), name='1 мая')
        client = Client()
        client.force_login(regular_user)
        resp = client.get('/api/holidays/')
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_regular_user_cannot_create(self, regular_user):
        client = Client()
        client.force_login(regular_user)
        resp = client.post(
            '/api/holidays/',
            json.dumps({'date': '2026-06-12', 'name': 'test'}),
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_unauthenticated_401(self):
        client = Client()
        resp = client.get('/api/holidays/')
        assert resp.status_code == 401
