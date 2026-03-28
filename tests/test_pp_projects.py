"""
Тесты API проектов ПП (PPProject).
Покрытие: GET /api/pp_projects/, POST /api/pp_projects/create/,
          PUT/DELETE /api/pp_projects/<pk>/
"""
import json

import pytest
from django.test import Client

from apps.works.models import PPProject, Project


@pytest.fixture
def project(db):
    """УП-проект для привязки к ПП-проекту."""
    return Project.objects.create(name_full='Тестовый проект')


@pytest.fixture
def pp_project(db, project):
    """Существующий ПП-проект."""
    return PPProject.objects.create(
        name='План 2026',
        up_project=project,
    )


class TestPPProjectList:
    def test_anon_401(self):
        c = Client()
        r = c.get('/api/pp_projects/')
        assert r.status_code == 401

    def test_list_success(self, admin_user, pp_project):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.get('/api/pp_projects/')
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get('pp_projects', data.get('results', []))
        assert len(items) >= 1


class TestPPProjectCreate:
    def test_anon_401(self):
        c = Client()
        r = c.post('/api/pp_projects/create/', '{}', content_type='application/json')
        assert r.status_code == 401

    def test_regular_user_403(self, regular_user):
        c = Client()
        c.login(username='user_test', password='testpass123')
        r = c.post('/api/pp_projects/create/',
                   json.dumps({'name': 'X'}),
                   content_type='application/json')
        assert r.status_code == 403

    def test_create_success(self, admin_user, project):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.post('/api/pp_projects/create/',
                   json.dumps({
                       'name': 'Новый план',
                       'up_project_id': project.id,
                   }),
                   content_type='application/json')
        assert r.status_code in (200, 201)
        assert PPProject.objects.filter(name='Новый план').exists()


class TestPPProjectDetail:
    def test_update_success(self, admin_user, pp_project):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.put(f'/api/pp_projects/{pp_project.id}/',
                  json.dumps({'name': 'Обновлённый план'}),
                  content_type='application/json')
        assert r.status_code == 200
        pp_project.refresh_from_db()
        assert pp_project.name == 'Обновлённый план'

    def test_delete_success(self, admin_user, pp_project):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.delete(f'/api/pp_projects/{pp_project.id}/')
        assert r.status_code == 200
        assert not PPProject.objects.filter(id=pp_project.id).exists()

    def test_delete_nonexistent(self, admin_user):
        c = Client()
        c.login(username='admin_test', password='testpass123')
        r = c.delete('/api/pp_projects/999999/')
        assert r.status_code == 404
