"""
Тесты CRUD API для модуля «Управление проектами» (Project + ProjectProduct).
Эндпоинты: /api/projects/, /api/projects/<id>/products/.
"""
import json

import pytest
from django.test import Client

from apps.works.models import Project, ProjectProduct


# ── Фикстуры ────────────────────────────────────────────────────────────────

@pytest.fixture
def project(db):
    """Тестовый УП-проект."""
    return Project.objects.create(
        name_full='Разработка системы управления БПЛА',
        name_short='СУ-БПЛА',
        code='КД-2026-001',
    )


@pytest.fixture
def product(db, project):
    """Тестовое изделие в рамках проекта."""
    return ProjectProduct.objects.create(
        project=project,
        name='Блок питания БП-12',
        code='ИЗД-001',
    )


# ── Список проектов ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProjectList:
    def test_admin_list(self, admin_user, project):
        client = Client()
        client.force_login(admin_user)
        resp = client.get('/api/projects/')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        names = [p['name_full'] for p in data]
        assert project.name_full in names

    def test_authenticated_can_list(self, regular_user, project):
        """Любой авторизованный пользователь может просматривать проекты."""
        client = Client()
        client.force_login(regular_user)
        resp = client.get('/api/projects/')
        assert resp.status_code == 200

    def test_unauthenticated_cannot_list(self):
        client = Client()
        resp = client.get('/api/projects/')
        assert resp.status_code == 401


# ── Создание проекта ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProjectCreate:
    def test_admin_create_ok(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            '/api/projects/create/',
            data=json.dumps({
                'name_full': 'Модернизация комплекса связи «Волна»',
                'name_short': 'КС-Волна',
                'code': 'КД-2026-007',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['name_full'] == 'Модернизация комплекса связи «Волна»'
        assert data['name_short'] == 'КС-Волна'
        assert data['code'] == 'КД-2026-007'
        # Проект должен существовать в БД
        assert Project.objects.filter(pk=data['id']).exists()

    def test_create_without_name_full_fails(self, admin_user):
        """Полное наименование обязательно."""
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            '/api/projects/create/',
            data=json.dumps({'name_short': 'Только краткое'}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_create_name_short_optional(self, admin_user):
        """Краткое наименование необязательно."""
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            '/api/projects/create/',
            data=json.dumps({'name_full': 'Проект без краткого имени'}),
            content_type='application/json',
        )
        assert resp.status_code == 201

    def test_dept_head_cannot_create(self, dept_head_user):
        """Создание проекта — только admin."""
        client = Client()
        client.force_login(dept_head_user)
        resp = client.post(
            '/api/projects/create/',
            data=json.dumps({'name_full': 'Попытка не-админа'}),
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_regular_user_cannot_create(self, regular_user):
        client = Client()
        client.force_login(regular_user)
        resp = client.post(
            '/api/projects/create/',
            data=json.dumps({'name_full': 'Попытка исполнителя'}),
            content_type='application/json',
        )
        assert resp.status_code == 403


# ── Обновление проекта ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProjectUpdate:
    def test_admin_update_ok(self, admin_user, project):
        client = Client()
        client.force_login(admin_user)
        resp = client.put(
            f'/api/projects/{project.id}/',
            data=json.dumps({
                'name_full': 'Обновлённое полное название',
                'name_short': 'ОбнПрНаз',
                'code': 'КД-2026-UPD',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        project.refresh_from_db()
        assert project.name_full == 'Обновлённое полное название'
        assert project.name_short == 'ОбнПрНаз'
        assert project.code == 'КД-2026-UPD'

    def test_update_nonexistent_returns_404(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        resp = client.put(
            '/api/projects/999999/',
            data=json.dumps({'name_full': 'Тест'}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_update_without_name_full_fails(self, admin_user, project):
        """Обновление без полного наименования — 400."""
        client = Client()
        client.force_login(admin_user)
        resp = client.put(
            f'/api/projects/{project.id}/',
            data=json.dumps({'name_short': 'Только краткое'}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_dept_head_cannot_update(self, dept_head_user, project):
        client = Client()
        client.force_login(dept_head_user)
        resp = client.put(
            f'/api/projects/{project.id}/',
            data=json.dumps({'name_full': 'Попытка'}),
            content_type='application/json',
        )
        assert resp.status_code == 403


# ── Удаление проекта ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProjectDelete:
    def test_admin_delete_ok(self, admin_user):
        proj = Project.objects.create(
            name_full='Проект для удаления',
            name_short='Удал',
        )
        proj_id = proj.id
        client = Client()
        client.force_login(admin_user)
        resp = client.delete(f'/api/projects/{proj_id}/')
        assert resp.status_code == 200
        assert not Project.objects.filter(pk=proj_id).exists()

    def test_delete_nonexistent_returns_404(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        resp = client.delete('/api/projects/999999/')
        assert resp.status_code == 404

    def test_dept_head_cannot_delete(self, dept_head_user, project):
        client = Client()
        client.force_login(dept_head_user)
        resp = client.delete(f'/api/projects/{project.id}/')
        assert resp.status_code == 403

    def test_cascade_deletes_products(self, admin_user, project, product):
        """Удаление проекта каскадно удаляет изделия."""
        product_id = product.id
        client = Client()
        client.force_login(admin_user)
        resp = client.delete(f'/api/projects/{project.id}/')
        assert resp.status_code == 200
        assert not ProjectProduct.objects.filter(pk=product_id).exists()


# ── CRUD для изделий (ProductProduct) ────────────────────────────────────────

@pytest.mark.django_db
class TestProjectProductList:
    def test_list_products(self, admin_user, project, product):
        client = Client()
        client.force_login(admin_user)
        resp = client.get(f'/api/projects/{project.id}/products/')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['name'] == 'Блок питания БП-12'

    def test_list_products_nonexistent_project(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        resp = client.get('/api/projects/999999/products/')
        assert resp.status_code == 404


@pytest.mark.django_db
class TestProjectProductCreate:
    def test_create_product_ok(self, admin_user, project):
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            f'/api/projects/{project.id}/products/create/',
            data=json.dumps({
                'name': 'Модуль навигации МН-3',
                'code': 'ИЗД-002',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['name'] == 'Модуль навигации МН-3'
        assert data['code'] == 'ИЗД-002'
        assert ProjectProduct.objects.filter(pk=data['id']).exists()

    def test_create_product_without_name_fails(self, admin_user, project):
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            f'/api/projects/{project.id}/products/create/',
            data=json.dumps({'code': 'ИЗД-003'}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_dept_head_cannot_create_product(self, dept_head_user, project):
        client = Client()
        client.force_login(dept_head_user)
        resp = client.post(
            f'/api/projects/{project.id}/products/create/',
            data=json.dumps({'name': 'Тестовое изделие'}),
            content_type='application/json',
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestProjectProductUpdate:
    def test_update_product_ok(self, admin_user, project, product):
        client = Client()
        client.force_login(admin_user)
        resp = client.put(
            f'/api/projects/{project.id}/products/{product.id}/',
            data=json.dumps({
                'name': 'Блок питания БП-24 (обновлённый)',
                'code': 'ИЗД-001-v2',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        product.refresh_from_db()
        assert product.name == 'Блок питания БП-24 (обновлённый)'
        assert product.code == 'ИЗД-001-v2'

    def test_update_nonexistent_product(self, admin_user, project):
        client = Client()
        client.force_login(admin_user)
        resp = client.put(
            f'/api/projects/{project.id}/products/999999/',
            data=json.dumps({'name': 'Тест'}),
            content_type='application/json',
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestProjectProductDelete:
    def test_delete_product_ok(self, admin_user, project, product):
        product_id = product.id
        client = Client()
        client.force_login(admin_user)
        resp = client.delete(
            f'/api/projects/{project.id}/products/{product_id}/'
        )
        assert resp.status_code == 200
        assert not ProjectProduct.objects.filter(pk=product_id).exists()

    def test_delete_nonexistent_product(self, admin_user, project):
        client = Client()
        client.force_login(admin_user)
        resp = client.delete(
            f'/api/projects/{project.id}/products/999999/'
        )
        assert resp.status_code == 404

    def test_dept_head_cannot_delete_product(self, dept_head_user, project, product):
        client = Client()
        client.force_login(dept_head_user)
        resp = client.delete(
            f'/api/projects/{project.id}/products/{product.id}/'
        )
        assert resp.status_code == 403
