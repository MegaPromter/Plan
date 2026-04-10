"""
Тесты Directories API.
"""

import json

import pytest
from django.test import Client

from apps.works.models import Directory


@pytest.fixture
def task_type_entry(db):
    return Directory.objects.create(
        dir_type="task_type",
        value="Разработка чертежа",
        parent=None,
    )


@pytest.mark.django_db
class TestDirectoryList:
    def test_requires_auth(self):
        resp = Client().get("/api/directories/")
        assert resp.status_code == 401

    def test_list_returns_data(self, admin_user, task_type_entry):
        c = Client()
        c.force_login(admin_user)
        resp = c.get("/api/directories/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        # Должны быть виртуальные секции (center, dept, sector и т.д.)
        assert "center" in data or "task_type" in data

    def test_regular_user_can_list(self, regular_user, task_type_entry):
        c = Client()
        c.force_login(regular_user)
        resp = c.get("/api/directories/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestDirectoryCreate:
    def test_create_entry(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.post(
            "/api/directories/create/",
            json.dumps({"type": "milestone", "value": "Новая веха"}),
            content_type="application/json",
        )
        assert resp.status_code == 201
        assert Directory.objects.filter(
            dir_type="milestone", value="Новая веха"
        ).exists()

    def test_rejects_reserved_type(self, admin_user):
        """center/dept/sector/task_type управляются виртуально."""
        c = Client()
        c.force_login(admin_user)
        for reserved in ("center", "task_type"):
            resp = c.post(
                "/api/directories/create/",
                json.dumps({"type": reserved, "value": "Хак"}),
                content_type="application/json",
            )
            assert resp.status_code == 400

    def test_requires_admin(self, regular_user):
        c = Client()
        c.force_login(regular_user)
        resp = c.post(
            "/api/directories/create/",
            json.dumps({"type": "task_type", "value": "X"}),
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_missing_type_400(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.post(
            "/api/directories/create/",
            json.dumps({"value": "Без типа"}),
            content_type="application/json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestDirectoryDetail:
    def test_update_entry(self, admin_user, task_type_entry):
        c = Client()
        c.force_login(admin_user)
        resp = c.put(
            f"/api/directories/{task_type_entry.id}/",
            json.dumps({"value": "Обновлённый тип"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        task_type_entry.refresh_from_db()
        assert task_type_entry.value == "Обновлённый тип"

    def test_delete_entry(self, admin_user, task_type_entry):
        c = Client()
        c.force_login(admin_user)
        resp = c.delete(f"/api/directories/{task_type_entry.id}/")
        assert resp.status_code == 200
        assert not Directory.objects.filter(id=task_type_entry.id).exists()

    def test_not_found_404(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.delete("/api/directories/99999/")
        assert resp.status_code == 404
