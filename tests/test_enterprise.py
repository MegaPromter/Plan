"""
Тесты API модуля «Управление предприятием» (enterprise).

Покрытие:
- Портфель: список, обновление, приоритеты, авторизация
- ГГ: CRUD (создание, этапы, вехи, удаление)
- Сквозной график: CRUD, edit_lock
- Baseline: создание снимков
- Capacity: расчёт загрузки
- Уведомления: список, пометка
"""
import json

import pytest
from django.test import Client

from apps.enterprise.models import (
    EnterpriseNotification,
)
from apps.works.models import Project

pytestmark = pytest.mark.django_db

API = '/api/enterprise'


# ── Фикстуры ────────────────────────────────────────────────────────────

@pytest.fixture
def project(db):
    return Project.objects.create(
        name_full='Тестовый проект',
        name_short='ТП',
        code='TP-001',
    )


@pytest.fixture
def admin_client(admin_user):
    c = Client()
    c.login(username='admin_test', password='testpass123')
    return c


@pytest.fixture
def writer_client(dept_head_user):
    c = Client()
    c.login(username='dept_head_test', password='testpass123')
    return c


@pytest.fixture
def reader_client(regular_user):
    c = Client()
    c.login(username='user_test', password='testpass123')
    return c


@pytest.fixture
def anon_client():
    return Client()


def _post(client, url, data=None):
    return client.post(url, json.dumps(data or {}), content_type='application/json')


def _put(client, url, data=None):
    return client.put(url, json.dumps(data or {}), content_type='application/json')


# ══════════════════════════════════════════════════════════════════════════
#  ПОРТФЕЛЬ
# ══════════════════════════════════════════════════════════════════════════

class TestPortfolio:
    def test_list_requires_auth(self, anon_client):
        r = anon_client.get(f'{API}/portfolio/')
        assert r.status_code == 401

    def test_list_returns_projects(self, reader_client, project):
        r = reader_client.get(f'{API}/portfolio/')
        assert r.status_code == 200
        data = r.json()
        assert len(data['projects']) == 1
        assert data['projects'][0]['code'] == 'TP-001'

    def test_list_filter_by_status(self, reader_client, project):
        project.status = 'closed'
        project.save(update_fields=['status'])
        r = reader_client.get(f'{API}/portfolio/?status=closed')
        assert len(r.json()['projects']) == 1
        r = reader_client.get(f'{API}/portfolio/?status=active')
        assert len(r.json()['projects']) == 0

    def test_update_requires_writer(self, reader_client, project):
        r = _put(reader_client, f'{API}/portfolio/{project.id}/', {'status': 'closed'})
        assert r.status_code == 403

    def test_update_status(self, writer_client, project):
        r = _put(writer_client, f'{API}/portfolio/{project.id}/', {'status': 'suspended'})
        assert r.status_code == 200
        project.refresh_from_db()
        assert project.status == 'suspended'

    def test_update_invalid_status(self, writer_client, project):
        r = _put(writer_client, f'{API}/portfolio/{project.id}/', {'status': 'invalid'})
        assert r.status_code == 400

    def test_priority(self, admin_client, project):
        r = _post(admin_client, f'{API}/portfolio/{project.id}/priority/', {
            'priority_number': 1,
            'priority_category': 'critical',
        })
        assert r.status_code == 200
        project.refresh_from_db()
        assert project.priority_number == 1
        assert project.priority_category == 'critical'

    def test_priority_requires_admin(self, writer_client, project):
        r = _post(writer_client, f'{API}/portfolio/{project.id}/priority/', {
            'priority_number': 1,
        })
        assert r.status_code == 403


# ══════════════════════════════════════════════════════════════════════════
#  ГЕНЕРАЛЬНЫЙ ГРАФИК
# ══════════════════════════════════════════════════════════════════════════

class TestGG:
    def test_get_empty(self, reader_client, project):
        r = reader_client.get(f'{API}/gg/{project.id}/')
        assert r.status_code == 200
        assert r.json()['schedule'] is None

    def test_create_gg(self, writer_client, project):
        r = _post(writer_client, f'{API}/gg/{project.id}/')
        assert r.status_code == 201
        assert r.json()['schedule']['project_id'] == project.id

    def test_create_gg_duplicate(self, writer_client, project):
        _post(writer_client, f'{API}/gg/{project.id}/')
        r = _post(writer_client, f'{API}/gg/{project.id}/')
        assert r.status_code == 400

    def test_create_stage(self, writer_client, project):
        _post(writer_client, f'{API}/gg/{project.id}/')
        r = _post(writer_client, f'{API}/gg/{project.id}/stages/', {
            'name': 'Этап 1',
            'date_start': '2026-04-01',
            'date_end': '2026-06-30',
            'labor': 100,
        })
        assert r.status_code == 201
        assert r.json()['stage']['name'] == 'Этап 1'

    def test_delete_stage(self, writer_client, project):
        _post(writer_client, f'{API}/gg/{project.id}/')
        r = _post(writer_client, f'{API}/gg/{project.id}/stages/', {'name': 'X'})
        stage_id = r.json()['stage']['id']
        r = writer_client.delete(f'{API}/gg_stages/{stage_id}/')
        assert r.status_code == 200

    def test_create_milestone(self, writer_client, project):
        _post(writer_client, f'{API}/gg/{project.id}/')
        r = _post(writer_client, f'{API}/gg/{project.id}/milestones/', {
            'name': 'КТ-1',
            'date': '2026-05-01',
        })
        assert r.status_code == 201

    def test_reader_cannot_create(self, reader_client, project):
        r = _post(reader_client, f'{API}/gg/{project.id}/')
        assert r.status_code == 403


# ══════════════════════════════════════════════════════════════════════════
#  СКВОЗНОЙ ГРАФИК
# ══════════════════════════════════════════════════════════════════════════

class TestCrossSchedule:
    def test_get_empty(self, reader_client, project):
        r = reader_client.get(f'{API}/cross/{project.id}/')
        assert r.status_code == 200
        assert r.json()['schedule'] is None

    def test_create(self, writer_client, project):
        r = _post(writer_client, f'{API}/cross/{project.id}/')
        assert r.status_code == 201
        assert r.json()['schedule']['edit_owner'] == 'cross'

    def test_edit_lock(self, writer_client, project):
        _post(writer_client, f'{API}/cross/{project.id}/')
        r = _put(writer_client, f'{API}/cross/{project.id}/', {'edit_owner': 'locked'})
        assert r.status_code == 200
        assert r.json()['schedule']['edit_owner'] == 'locked'

    def test_locked_prevents_stage_create(self, writer_client, project):
        _post(writer_client, f'{API}/cross/{project.id}/')
        _put(writer_client, f'{API}/cross/{project.id}/', {'edit_owner': 'locked'})
        r = _post(writer_client, f'{API}/cross/{project.id}/stages/', {'name': 'Test'})
        assert r.status_code == 403

    def test_create_from_gg(self, writer_client, project):
        """Создание сквозного графика с копированием этапов из ГГ."""
        _post(writer_client, f'{API}/gg/{project.id}/')
        _post(writer_client, f'{API}/gg/{project.id}/stages/', {'name': 'GG-Stage-1'})

        r = _post(writer_client, f'{API}/cross/{project.id}/', {'from_gg': True})
        assert r.status_code == 201
        stages = r.json()['schedule']['stages']
        assert len(stages) == 1
        assert stages[0]['name'] == 'GG-Stage-1'

    def test_create_stage_and_milestone(self, writer_client, project):
        _post(writer_client, f'{API}/cross/{project.id}/')
        r = _post(writer_client, f'{API}/cross/{project.id}/stages/', {'name': 'S1'})
        assert r.status_code == 201
        stage_id = r.json()['stage']['id']

        r = _post(writer_client, f'{API}/cross/{project.id}/milestones/', {
            'name': 'M1',
            'date': '2026-06-01',
            'cross_stage_id': stage_id,
        })
        assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════
#  BASELINE
# ══════════════════════════════════════════════════════════════════════════

class TestBaseline:
    def test_create_baseline(self, writer_client, project):
        _post(writer_client, f'{API}/cross/{project.id}/')
        r = _post(writer_client, f'{API}/cross/{project.id}/baselines/', {
            'comment': 'Версия 1',
        })
        assert r.status_code == 201
        assert r.json()['baseline']['version'] == 1

    def test_list_baselines(self, writer_client, project):
        _post(writer_client, f'{API}/cross/{project.id}/')
        _post(writer_client, f'{API}/cross/{project.id}/baselines/', {'comment': 'v1'})
        _post(writer_client, f'{API}/cross/{project.id}/baselines/', {'comment': 'v2'})

        r = writer_client.get(f'{API}/cross/{project.id}/baselines/')
        assert r.status_code == 200
        assert len(r.json()['baselines']) == 2

    def test_view_baseline_detail(self, writer_client, project):
        _post(writer_client, f'{API}/cross/{project.id}/')
        r = _post(writer_client, f'{API}/cross/{project.id}/baselines/', {'comment': 'v1'})
        bl_id = r.json()['baseline']['id']

        r = writer_client.get(f'{API}/baselines/{bl_id}/')
        assert r.status_code == 200
        assert 'entries' in r.json()['baseline']


# ══════════════════════════════════════════════════════════════════════════
#  CAPACITY (ЗАГРУЗКА)
# ══════════════════════════════════════════════════════════════════════════

class TestCapacity:
    def test_capacity_requires_auth(self, anon_client):
        r = anon_client.get(f'{API}/capacity/')
        assert r.status_code == 401

    def test_capacity_returns_data(self, reader_client, dept):
        r = reader_client.get(f'{API}/capacity/?year=2026')
        assert r.status_code == 200
        data = r.json()
        assert data['year'] == 2026
        assert isinstance(data['centers'], list)
        # Отдел из фикстуры должен быть в результате (в центрах или без центра)
        dept_names = []
        for c in data['centers']:
            dept_names += [d['department_name'] for d in c['departments']]
        dept_names += [d['department_name'] for d in data.get('no_center_departments', [])]
        assert 'Тестовый отдел' in dept_names


# ══════════════════════════════════════════════════════════════════════════
#  УВЕДОМЛЕНИЯ
# ══════════════════════════════════════════════════════════════════════════

class TestEntNotifications:
    def test_list_empty(self, reader_client):
        r = reader_client.get(f'{API}/notifications/')
        assert r.status_code == 200
        assert r.json()['notifications'] == []

    def test_mark_read(self, reader_client, regular_user):
        emp = regular_user.employee
        n = EnterpriseNotification.objects.create(
            recipient=emp,
            notification_type='phase_change',
            title='Тест',
        )
        r = _post(reader_client, f'{API}/notifications/{n.id}/read/')
        assert r.status_code == 200
        n.refresh_from_db()
        assert n.is_read is True

    def test_read_all(self, reader_client, regular_user):
        emp = regular_user.employee
        for i in range(3):
            EnterpriseNotification.objects.create(
                recipient=emp,
                notification_type='phase_change',
                title=f'Тест {i}',
            )
        r = _post(reader_client, f'{API}/notifications/read_all/')
        assert r.status_code == 200
        assert r.json()['updated'] == 3

    def test_unread_count(self, reader_client, regular_user):
        emp = regular_user.employee
        EnterpriseNotification.objects.create(
            recipient=emp, notification_type='phase_change', title='X',
        )
        r = reader_client.get(f'{API}/notifications/unread_count/')
        assert r.json()['count'] == 1


# ══════════════════════════════════════════════════════════════════════════
#  СЦЕНАРИИ
# ══════════════════════════════════════════════════════════════════════════

class TestScenarios:
    def test_crud(self, writer_client, project):
        # Create
        r = _post(writer_client, f'{API}/scenarios/', {
            'name': 'Сценарий A',
            'project_id': project.id,
        })
        assert r.status_code == 201
        sc_id = r.json()['scenario']['id']

        # Read
        r = writer_client.get(f'{API}/scenarios/{sc_id}/')
        assert r.status_code == 200
        assert r.json()['scenario']['name'] == 'Сценарий A'

        # Update
        r = _put(writer_client, f'{API}/scenarios/{sc_id}/', {'status': 'active'})
        assert r.status_code == 200

        # List
        r = writer_client.get(f'{API}/scenarios/')
        assert len(r.json()['scenarios']) == 1

        # Add entry
        r = _post(writer_client, f'{API}/scenarios/{sc_id}/entries/', {
            'data': {'labor': 100, 'note': 'test'},
        })
        assert r.status_code == 201

        # Delete
        r = writer_client.delete(f'{API}/scenarios/{sc_id}/')
        assert r.status_code == 200

    def test_reader_cannot_create(self, reader_client):
        r = _post(reader_client, f'{API}/scenarios/', {'name': 'X'})
        assert r.status_code == 403
