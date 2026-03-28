"""
Тесты API журнала аудита.
Покрытие: GET /api/audit_log/
"""
from django.test import Client


class TestAuditLogList:
    def test_anon_401(self):
        c = Client()
        r = c.get('/api/audit_log/')
        assert r.status_code == 401

    def test_regular_user_403(self, regular_user):
        c = Client()
        c.login(username='user_test', password='testpass123')
        r = c.get('/api/audit_log/')
        assert r.status_code == 403

    def test_admin_success(self, admin_user):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.get('/api/audit_log/')
        assert r.status_code == 200
        data = r.json()
        assert 'items' in data
        assert data['total'] == 0
