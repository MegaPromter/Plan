"""
Тесты API аналитики.
Покрытие: GET /api/analytics/workload/, /api/analytics/employee/, /api/analytics/pp/
"""
import pytest
from django.test import Client


class TestWorkloadAnalytics:
    def test_anon_401(self):
        c = Client()
        r = c.get('/api/analytics/workload/')
        assert r.status_code == 401

    def test_success(self, admin_user):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.get('/api/analytics/workload/')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)


class TestEmployeeAnalytics:
    def test_anon_401(self):
        c = Client()
        r = c.get('/api/analytics/employee/')
        assert r.status_code == 401

    def test_success(self, admin_user):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.get('/api/analytics/employee/')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)


class TestPPAnalytics:
    def test_anon_401(self):
        c = Client()
        r = c.get('/api/analytics/pp/')
        assert r.status_code == 401

    def test_success(self, admin_user):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.get('/api/analytics/pp/')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
