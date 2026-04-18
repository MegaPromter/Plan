"""
Тесты API отчётных документов (WorkReport).
Покрытие: POST /api/reports/, GET /api/reports/<task_id>/,
          PUT/DELETE /api/reports/<pk>/detail/
"""

import json

import pytest
from django.test import Client

from apps.works.models import Work, WorkReport


@pytest.fixture
def work(db, dept):
    """Задача для привязки отчётов."""
    return Work.objects.create(
        work_name="Тестовая работа",
        show_in_plan=True,
        department=dept,
    )


@pytest.fixture
def report(db, work):
    """Существующий отчёт."""
    return WorkReport.objects.create(
        work=work,
        doc_name="Тестовый документ",
        doc_designation="АБВГ.001",
        ii_pi="ИИ",
        doc_number="123",
    )


# ── GET /api/reports/<task_id>/ ──────────────────────────────────────────────


class TestReportList:
    def test_anon_401(self):
        c = Client()
        r = c.get("/api/reports/1/")
        assert r.status_code == 401

    def test_list_empty(self, admin_user, work):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get(f"/api/reports/{work.id}/")
        assert r.status_code == 200
        data = r.json()
        assert data == []

    def test_list_with_report(self, admin_user, work, report):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get(f"/api/reports/{work.id}/")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["doc_name"] == "Тестовый документ"


# ── POST /api/reports/ ───────────────────────────────────────────────────────


class TestReportCreate:
    def test_anon_401(self):
        c = Client()
        r = c.post("/api/reports/", "{}", content_type="application/json")
        assert r.status_code == 401

    def test_regular_user_not_executor_403(self, regular_user, work):
        """Рядовой user, не назначенный исполнителем, получает 403."""
        c = Client()
        c.login(username="user_test", password="testpass123")
        r = c.post(
            "/api/reports/",
            json.dumps({"task_id": work.id, "doc_name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 403

    def test_regular_user_as_executor_can_create(self, regular_user, work):
        """Рядовой user, назначенный исполнителем задачи, может создать отчёт."""
        emp = regular_user.employee
        work.executor = emp
        work.save(update_fields=["executor"])
        c = Client()
        c.login(username="user_test", password="testpass123")
        r = c.post(
            "/api/reports/",
            json.dumps(
                {
                    "task_id": work.id,
                    "doc_name": "Отчёт исполнителя",
                    "ii_pi": "ИИ",
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 200, r.content

    def test_regular_user_as_task_executor_can_create(self, regular_user, work):
        """Рядовой user, добавленный как доп. исполнитель (TaskExecutor), может создать отчёт."""
        from apps.works.models import TaskExecutor

        TaskExecutor.objects.create(
            work=work,
            executor=regular_user.employee,
            executor_name=regular_user.employee.full_name,
        )
        c = Client()
        c.login(username="user_test", password="testpass123")
        r = c.post(
            "/api/reports/",
            json.dumps(
                {
                    "task_id": work.id,
                    "doc_name": "Отчёт соисполнителя",
                    "ii_pi": "ИИ",
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 200, r.content

    def test_create_rejects_future_plan_hours_without_confirm(self, admin_user, work):
        """Если у задачи есть часы в будущих месяцах, первый POST возвращает 409."""
        import datetime as dt

        # Ставим часы на год вперёд
        next_year = dt.date.today().year + 1
        work.plan_hours = {f"{next_year}-01": 40, f"{next_year}-02": 20}
        work.save(update_fields=["plan_hours"])

        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.post(
            "/api/reports/",
            json.dumps({"task_id": work.id, "doc_name": "Ранний отчёт", "ii_pi": "ИИ"}),
            content_type="application/json",
        )
        assert r.status_code == 409
        data = r.json()
        assert data.get("error") == "confirm_zero_future_required"
        assert f"{next_year}-01" in data.get("future_months", [])

    def test_create_with_confirm_zero_future_succeeds(self, admin_user, work):
        """С флагом confirm_zero_future=true сохраняем и обнуляем будущие месяцы."""
        import datetime as dt

        next_year = dt.date.today().year + 1
        work.plan_hours = {f"{next_year}-01": 40}
        work.save(update_fields=["plan_hours"])

        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.post(
            "/api/reports/",
            json.dumps(
                {
                    "task_id": work.id,
                    "doc_name": "Досрочный",
                    "ii_pi": "ИИ",
                    "confirm_zero_future": True,
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 200, r.content
        work.refresh_from_db()
        assert work.plan_hours[f"{next_year}-01"] == 0

    def test_create_success(self, admin_user, work):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.post(
            "/api/reports/",
            json.dumps(
                {
                    "task_id": work.id,
                    "doc_name": "Новый документ",
                    "doc_designation": "АБВГ.002",
                    "ii_pi": "ПИ",
                    "doc_number": "456",
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert WorkReport.objects.filter(id=data["id"]).exists()

    def test_create_missing_task_id(self, admin_user):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.post(
            "/api/reports/",
            json.dumps({"doc_name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_create_invalid_task_id(self, admin_user):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.post(
            "/api/reports/",
            json.dumps({"task_id": 999999, "doc_name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 404


# ── PUT /api/reports/<pk>/detail/ ────────────────────────────────────────────


class TestReportUpdate:
    def test_update_success(self, admin_user, report):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.put(
            f"/api/reports/{report.id}/detail/",
            json.dumps({"doc_name": "Обновлённый"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        report.refresh_from_db()
        assert report.doc_name == "Обновлённый"

    def test_update_nonexistent(self, admin_user):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.put(
            "/api/reports/999999/detail/",
            json.dumps({"doc_name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 404


# ── DELETE /api/reports/<pk>/detail/ ─────────────────────────────────────────


class TestReportDelete:
    def test_delete_success(self, admin_user, report):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.delete(f"/api/reports/{report.id}/detail/")
        assert r.status_code == 200
        assert not WorkReport.objects.filter(id=report.id).exists()

    def test_delete_nonexistent(self, admin_user):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.delete("/api/reports/999999/detail/")
        assert r.status_code == 404
