"""
Тесты массовых операций с задачами.
Покрытие: DELETE /api/tasks/all/, POST /api/tasks/bulk_delete/,
          GET /api/dept_employees/, GET /api/tasks/<pk>/executors/
"""
import json

import pytest
from django.test import Client

from apps.works.models import Work


@pytest.fixture
def tasks(db, dept):
    """3 задачи для массовых операций."""
    return [
        Work.objects.create(work_name=f'Задача {i}', show_in_plan=True, department=dept)
        for i in range(3)
    ]


# ── DELETE /api/tasks/all/ ───────────────────────────────────────────────────

class TestTaskDeleteAll:
    def test_anon_401(self):
        c = Client()
        r = c.delete('/api/tasks/all/')
        assert r.status_code == 401

    def test_regular_user_403(self, regular_user, tasks):
        c = Client()
        c.login(username='user_test', password='testpass123')
        r = c.delete('/api/tasks/all/')
        assert r.status_code == 403

    def test_admin_success(self, admin_user, tasks):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.delete('/api/tasks/all/')
        assert r.status_code == 200
        assert Work.objects.filter(show_in_plan=True).count() == 0


# ── POST /api/tasks/bulk_delete/ ─────────────────────────────────────────────

class TestTaskBulkDelete:
    def test_anon_401(self):
        c = Client()
        r = c.post('/api/tasks/bulk_delete/', '{}', content_type='application/json')
        assert r.status_code == 401

    def test_regular_user_403(self, regular_user, tasks):
        c = Client()
        c.login(username='user_test', password='testpass123')
        ids = [t.id for t in tasks]
        r = c.post('/api/tasks/bulk_delete/',
                   json.dumps({'ids': ids}),
                   content_type='application/json')
        assert r.status_code == 403

    def test_admin_bulk_delete(self, admin_user, tasks):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        ids = [tasks[0].id, tasks[1].id]
        r = c.post('/api/tasks/bulk_delete/',
                   json.dumps({'ids': ids}),
                   content_type='application/json')
        assert r.status_code == 200
        assert Work.objects.filter(id__in=ids, show_in_plan=True).count() == 0
        # Третья задача осталась
        assert Work.objects.filter(id=tasks[2].id).exists()


# ── GET /api/dept_employees/ ─────────────────────────────────────────────────

class TestDeptEmployees:
    def test_anon_401(self):
        c = Client()
        r = c.get('/api/dept_employees/')
        assert r.status_code == 401

    def test_success(self, admin_user, dept):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.get(f'/api/dept_employees/?dept={dept.code}')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))


# ── GET /api/tasks/<pk>/executors/ ───────────────────────────────────────────

class TestTaskExecutors:
    def test_anon_401(self):
        c = Client()
        r = c.get('/api/tasks/1/executors/')
        assert r.status_code == 401

    def test_success(self, admin_user, tasks):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.get(f'/api/tasks/{tasks[0].id}/executors/')
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_nonexistent_task(self, admin_user):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.get('/api/tasks/999999/executors/')
        assert r.status_code in (403, 404)
