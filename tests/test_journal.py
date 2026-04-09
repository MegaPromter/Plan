"""
Тесты Journal API (Журнал извещений — Notice).
"""
import json

import pytest
from django.test import Client

from apps.works.models import Notice


@pytest.fixture
def notice(db, dept, sector):
    """Ручная запись ЖИ."""
    return Notice.objects.create(
        ii_pi='ИИ',
        notice_number='ИИ-001',
        subject='Тестовое извещение',
        doc_designation='ABC.123',
        department=dept,
        sector=sector,
        status='active',
    )


@pytest.mark.django_db
class TestJournalList:
    def test_list_requires_auth(self):
        resp = Client().get('/api/journal/')
        assert resp.status_code == 401

    def test_list_returns_data(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/journal/')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]['notice_number'] == 'ИИ-001'

    def test_list_filter_by_status(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/journal/?status=active')
        assert resp.status_code == 200
        assert all(n['status'] == 'active' for n in resp.json())

    def test_check_number_exists(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/journal/?check_number=ИИ-001&check_ii_pi=ИИ')
        assert resp.status_code == 200
        assert resp.json()['exists'] is True

    def test_check_number_not_exists(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/journal/?check_number=НЕСУЩЕСТВ&check_ii_pi=ПИ')
        assert resp.status_code == 200
        assert resp.json()['exists'] is False


@pytest.mark.django_db
class TestJournalFacets:
    def test_facets_requires_auth(self):
        resp = Client().get('/api/journal/facets/')
        assert resp.status_code == 401

    def test_facets_returns_columns(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/journal/facets/')
        assert resp.status_code == 200
        data = resp.json()
        assert 'ii_pi' in data
        assert 'dept' in data
        assert 'status' in data
        assert 'ИИ' in data['ii_pi']


@pytest.mark.django_db
class TestJournalPagination:
    def test_limit_offset(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/journal/?limit=10&offset=0')
        assert resp.status_code == 200
        assert 'X-Total-Count' in resp
        assert 'X-Has-More' in resp

    def test_sort_param(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/journal/?sort=-date_issued')
        assert resp.status_code == 200

    def test_mf_filter(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.get('/api/journal/?mf_ii_pi=ИИ')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(n['ii_pi'] == 'ИИ' for n in data)


@pytest.mark.django_db
class TestJournalCreate:
    def test_create_requires_writer(self, regular_user):
        c = Client()
        c.force_login(regular_user)
        resp = c.post('/api/journal/create/',
            json.dumps({'ii_pi': 'ИИ', 'notice_number': 'ИИ-002', 'subject': 'Тест'}),
            content_type='application/json')
        assert resp.status_code == 403

    def test_create_by_admin(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.post('/api/journal/create/',
            json.dumps({
                'ii_pi': 'ПИ', 'notice_number': 'ПИ-010',
                'subject': 'Новое извещение',
            }),
            content_type='application/json')
        assert resp.status_code == 201
        assert Notice.objects.filter(notice_number='ПИ-010').exists()


@pytest.mark.django_db
class TestJournalDetail:
    def test_update_notice(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.put(f'/api/journal/{notice.id}/',
            json.dumps({'subject': 'Обновлено'}),
            content_type='application/json')
        assert resp.status_code == 200
        notice.refresh_from_db()
        assert notice.subject == 'Обновлено'

    def test_delete_manual_notice(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.delete(f'/api/journal/{notice.id}/')
        assert resp.status_code == 200
        assert not Notice.objects.filter(id=notice.id).exists()

    def test_delete_not_found(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.delete('/api/journal/99999/')
        assert resp.status_code == 404

    def test_create_future_date_rejected(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.post('/api/journal/create/',
            json.dumps({
                'ii_pi': 'ИИ', 'notice_number': 'ИИ-FUT',
                'subject': 'Будущая дата', 'date_issued': '2099-01-01',
            }),
            content_type='application/json')
        assert resp.status_code == 400
        assert 'позже' in resp.json()['error']

    def test_update_future_date_rejected(self, admin_user, notice):
        c = Client()
        c.force_login(admin_user)
        resp = c.put(f'/api/journal/{notice.id}/',
            json.dumps({'date_issued': '2099-01-01'}),
            content_type='application/json')
        assert resp.status_code == 400
        assert 'позже' in resp.json()['error']

    def test_update_requires_writer(self, regular_user, notice):
        c = Client()
        c.force_login(regular_user)
        resp = c.put(f'/api/journal/{notice.id}/',
            json.dumps({'subject': 'Хак'}),
            content_type='application/json')
        assert resp.status_code == 403
