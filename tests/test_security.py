"""
Тесты безопасности API — аутентификация, авторизация, CSRF.

Проверяют:
  - 401 для неавторизованных запросов
  - 403 для обычных пользователей на writer/admin эндпоинтах
  - CSRF-защиту POST-запросов
  - Health check без авторизации
"""

import json

import pytest
from django.test import Client

# ── Неавторизованные запросы (401) ───────────────────────────────────────────


@pytest.mark.django_db
class TestUnauthenticated401:
    """Все защищённые API-эндпоинты возвращают 401 без аутентификации."""

    PROTECTED_GET_ENDPOINTS = [
        "/api/tasks/",
        "/api/production_plan/",
        "/api/projects/",
        "/api/pp_projects/",
        "/api/directories/",
        "/api/users/",
        "/api/vacations/",
        "/api/journal/",
        "/api/work_calendar/",
        "/api/col_settings/",
        "/api/dependencies/",
    ]

    PROTECTED_POST_ENDPOINTS = [
        "/api/tasks/create/",
        "/api/production_plan/create/",
        "/api/projects/create/",
        "/api/pp_projects/create/",
        "/api/directories/create/",
        "/api/vacations/create/",
        "/api/journal/create/",
        "/api/work_calendar/create/",
        "/api/production_plan/sync/",
    ]

    @pytest.mark.parametrize("url", PROTECTED_GET_ENDPOINTS)
    def test_get_returns_401(self, url):
        client = Client()
        resp = client.get(url)
        assert resp.status_code == 401, f"GET {url} должен вернуть 401"

    @pytest.mark.parametrize("url", PROTECTED_POST_ENDPOINTS)
    def test_post_returns_401(self, url):
        client = Client()
        resp = client.post(
            url,
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 401, f"POST {url} должен вернуть 401"

    def test_put_returns_401(self):
        client = Client()
        resp = client.put(
            "/api/production_plan/1/",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_delete_returns_401(self):
        client = Client()
        resp = client.delete("/api/production_plan/1/")
        assert resp.status_code == 401


# ── Обычный пользователь не может писать (403) ──────────────────────────────


@pytest.mark.django_db
class TestRegularUser403:
    """Обычный user (role='user') получает 403 на writer-эндпоинтах."""

    WRITER_POST_ENDPOINTS = [
        "/api/tasks/create/",
        "/api/production_plan/create/",
        "/api/vacations/create/",
        "/api/journal/create/",
    ]

    @pytest.mark.parametrize("url", WRITER_POST_ENDPOINTS)
    def test_regular_user_writer_403(self, regular_user, url):
        client = Client()
        client.force_login(regular_user)
        resp = client.post(
            url,
            data=json.dumps({"name": "test"}),
            content_type="application/json",
        )
        assert (
            resp.status_code == 403
        ), f"POST {url}: обычный пользователь должен получить 403"

    def test_regular_user_cannot_put_pp(self, regular_user):
        """PUT на writer-эндпоинт — 403."""
        client = Client()
        client.force_login(regular_user)
        resp = client.put(
            "/api/production_plan/1/?field=work_name",
            data=json.dumps({"value": "test"}),
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_regular_user_cannot_delete_pp(self, regular_user):
        """DELETE на writer-эндпоинт — 403."""
        client = Client()
        client.force_login(regular_user)
        resp = client.delete("/api/production_plan/1/")
        assert resp.status_code == 403


# ── Не-админ не проходит AdminRequired (403) ────────────────────────────────


@pytest.mark.django_db
class TestNonAdmin403:
    """Пользователь без роли admin получает 403 на admin-эндпоинтах."""

    def test_dept_head_cannot_create_directory(self, dept_head_user):
        client = Client()
        client.force_login(dept_head_user)
        resp = client.post(
            "/api/directories/create/",
            data=json.dumps({"dir_type": "task_type", "value": "Тест"}),
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_dept_head_cannot_manage_users(self, dept_head_user):
        client = Client()
        client.force_login(dept_head_user)
        resp = client.get("/api/users/")
        assert resp.status_code == 403

    def test_dept_head_cannot_create_project(self, dept_head_user):
        """Создание УП-проекта — только admin."""
        client = Client()
        client.force_login(dept_head_user)
        resp = client.post(
            "/api/projects/create/",
            data=json.dumps({"name_full": "Тестовый проект"}),
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_dept_head_cannot_delete_project(self, dept_head_user):
        client = Client()
        client.force_login(dept_head_user)
        resp = client.delete("/api/projects/1/")
        assert resp.status_code == 403

    def test_regular_user_cannot_create_pp_project(self, regular_user):
        """Создание проекта ПП — только admin."""
        client = Client()
        client.force_login(regular_user)
        resp = client.post(
            "/api/pp_projects/create/",
            data=json.dumps({"name": "Тест"}),
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_regular_user_cannot_create_work_calendar(self, regular_user):
        """Создание записи календаря — только admin."""
        client = Client()
        client.force_login(regular_user)
        resp = client.post(
            "/api/work_calendar/create/",
            data=json.dumps({"year": 2026, "month": 1, "hours_norm": 136}),
            content_type="application/json",
        )
        assert resp.status_code == 403


# ── CSRF-защита ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCSRFProtection:
    """POST-запросы без CSRF-токена отклоняются (enforce_csrf_checks=True)."""

    def test_post_without_csrf_rejected(self, admin_user):
        # Client с enforce_csrf_checks=True — строгая проверка CSRF
        client = Client(enforce_csrf_checks=True)
        client.force_login(admin_user)
        resp = client.post(
            "/api/pp_projects/create/",
            data=json.dumps({"name": "Тест CSRF"}),
            content_type="application/json",
        )
        # DRF SessionAuthentication отклоняет без CSRF как 401 (не authenticated),
        # Django View отклоняет как 403. Принимаем оба варианта.
        assert resp.status_code in (401, 403)

    def test_post_with_csrf_ok(self, admin_user):
        """POST с правильным CSRF-токеном проходит."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(admin_user)
        # Получаем CSRF-cookie через GET-запрос
        client.get("/api/pp_projects/")
        csrf_token = client.cookies.get("csrftoken")
        if csrf_token:
            resp = client.post(
                "/api/pp_projects/create/",
                data=json.dumps({"name": "Тест с CSRF"}),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=csrf_token.value,
            )
            # Должен пройти CSRF-проверку (200 или 201, не 403)
            assert resp.status_code != 403


# ── Health check без авторизации ─────────────────────────────────────────────


@pytest.mark.django_db
class TestHealthCheckAccess:
    def test_health_no_auth_200(self):
        client = Client()
        resp = client.get("/api/health/")
        assert resp.status_code == 200
