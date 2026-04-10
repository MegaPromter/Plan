"""
Тесты ролевой модели — is_writer и доступ к API.
"""

import json

import pytest
from django.test import Client


@pytest.mark.django_db
class TestEmployeeRoles:
    def test_admin_is_writer(self, admin_user):
        emp = admin_user.employee
        assert emp.is_writer is True

    def test_dept_head_is_writer(self, dept_head_user):
        emp = dept_head_user.employee
        assert emp.is_writer is True

    def test_regular_user_is_not_writer(self, regular_user):
        emp = regular_user.employee
        assert emp.is_writer is False

    def test_full_name_property(self, admin_user):
        emp = admin_user.employee
        assert emp.full_name == "Иванов Иван Иванович"

    def test_short_name_property(self, admin_user):
        emp = admin_user.employee
        assert emp.short_name == "Иванов И.И."


@pytest.mark.django_db
class TestApiPermissions:
    def test_unauthenticated_returns_401(self):
        client = Client()
        resp = client.get("/api/tasks/")
        assert resp.status_code == 401

    def test_authenticated_can_access_tasks(self, regular_user):
        client = Client()
        client.force_login(regular_user)
        resp = client.get("/api/tasks/")
        assert resp.status_code == 200

    def test_regular_user_cannot_create_pp_project(self, regular_user):
        client = Client()
        client.force_login(regular_user)
        resp = client.post(
            "/api/pp_projects/create/",
            data=json.dumps({"name": "Тест"}),
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_writer_can_create_pp_project(self, admin_user):
        # PPProjectCreateView требует AdminRequiredJsonMixin — только для админов
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            "/api/pp_projects/create/",
            data=json.dumps({"name": "Новый ПП план"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Новый ПП план"
