"""
Тесты проверки пересечения отпусков.
"""
import json
import pytest
from datetime import date

from django.test import Client

from apps.employees.models import Employee, Vacation


@pytest.mark.django_db
class TestVacationConflict:
    def test_no_conflict(self, dept_head_user):
        """Два непересекающихся отпуска — конфликта нет."""
        emp = dept_head_user.employee
        Vacation.objects.create(
            employee=emp,
            date_start=date(2025, 1, 10),
            date_end=date(2025, 1, 20),
        )
        client = Client()
        client.force_login(dept_head_user)
        resp = client.post(
            '/api/check_vacation_conflict/',
            data=json.dumps({
                'employee_id': emp.pk,
                'date_start': '2025-02-01',
                'date_end': '2025-02-10',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('conflict') is False

    def test_conflict_exists(self, dept_head_user):
        """Пересекающийся отпуск — конфликт есть."""
        emp = dept_head_user.employee
        Vacation.objects.create(
            employee=emp,
            date_start=date(2025, 3, 1),
            date_end=date(2025, 3, 31),
        )
        client = Client()
        client.force_login(dept_head_user)
        resp = client.post(
            '/api/check_vacation_conflict/',
            data=json.dumps({
                'employee_id': emp.pk,
                'date_start': '2025-03-15',
                'date_end': '2025-04-05',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('conflict') is True
