"""
Тесты API зависимостей задач (TaskDependency).
"""

import json
from datetime import date

import pytest
from django.test import Client

from apps.works.models import PPProject, TaskDependency, Work


@pytest.fixture
def writer_client(admin_user):
    c = Client()
    c.login(username="admin_test", password="testpass123")
    return c


@pytest.fixture
def reader_client(regular_user):
    c = Client()
    c.login(username="user_test", password="testpass123")
    return c


@pytest.fixture
def task_a(db, dept):
    return Work.objects.create(
        show_in_plan=True,
        work_name="Задача A",
        department=dept,
        date_start=date(2026, 1, 1),
        date_end=date(2026, 1, 10),
    )


@pytest.fixture
def task_b(db, dept):
    return Work.objects.create(
        show_in_plan=True,
        work_name="Задача B",
        department=dept,
        date_start=date(2026, 1, 5),
        date_end=date(2026, 1, 15),
    )


@pytest.fixture
def task_c(db, dept):
    return Work.objects.create(
        show_in_plan=True,
        work_name="Задача C",
        department=dept,
        date_start=date(2026, 1, 20),
        date_end=date(2026, 1, 30),
    )


@pytest.fixture
def pp_task(db, dept):
    """Задача только в ПП (не в плане)."""
    pp_proj = PPProject.objects.create(name="Тест ПП")
    return Work.objects.create(
        show_in_pp=True,
        show_in_plan=False,
        work_name="PP Only",
        department=dept,
        pp_project=pp_proj,
    )


# ── Создание зависимости ─────────────────────────────────────────────────


class TestCreateDependency:
    def test_create_ok(self, writer_client, task_a, task_b):
        resp = writer_client.post(
            f"/api/tasks/{task_b.id}/dependencies/",
            json.dumps({"predecessor_id": task_a.id}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert TaskDependency.objects.filter(
            predecessor=task_a,
            successor=task_b,
        ).exists()

    def test_create_with_type_and_lag(self, writer_client, task_a, task_b):
        resp = writer_client.post(
            f"/api/tasks/{task_b.id}/dependencies/",
            json.dumps(
                {
                    "predecessor_id": task_a.id,
                    "dep_type": "SS",
                    "lag_days": 3,
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200
        dep = TaskDependency.objects.get(pk=resp.json()["id"])
        assert dep.dep_type == "SS"
        assert dep.lag_days == 3

    def test_reader_cannot_create(self, reader_client, task_a, task_b):
        resp = reader_client.post(
            f"/api/tasks/{task_b.id}/dependencies/",
            json.dumps({"predecessor_id": task_a.id}),
            content_type="application/json",
        )
        assert resp.status_code == 403


# ── Дубликат и самоссылка ─────────────────────────────────────────────────


class TestDuplicateAndSelf:
    def test_duplicate_rejected(self, writer_client, task_a, task_b):
        TaskDependency.objects.create(
            predecessor=task_a,
            successor=task_b,
        )
        resp = writer_client.post(
            f"/api/tasks/{task_b.id}/dependencies/",
            json.dumps({"predecessor_id": task_a.id}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "уже существует" in resp.json()["error"]

    def test_self_dependency_rejected(self, writer_client, task_a):
        resp = writer_client.post(
            f"/api/tasks/{task_a.id}/dependencies/",
            json.dumps({"predecessor_id": task_a.id}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "от самой себя" in resp.json()["error"]


# ── Цикл ─────────────────────────────────────────────────────────────────


class TestCycleDetection:
    def test_direct_cycle(self, writer_client, task_a, task_b):
        # A → B
        TaskDependency.objects.create(
            predecessor=task_a,
            successor=task_b,
        )
        # B → A — цикл
        resp = writer_client.post(
            f"/api/tasks/{task_a.id}/dependencies/",
            json.dumps({"predecessor_id": task_b.id}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "цикл" in resp.json()["error"]

    def test_transitive_cycle(self, writer_client, task_a, task_b, task_c):
        # A → B → C
        TaskDependency.objects.create(
            predecessor=task_a,
            successor=task_b,
        )
        TaskDependency.objects.create(
            predecessor=task_b,
            successor=task_c,
        )
        # C → A — цикл
        resp = writer_client.post(
            f"/api/tasks/{task_a.id}/dependencies/",
            json.dumps({"predecessor_id": task_c.id}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "цикл" in resp.json()["error"]


# ── Список зависимостей ──────────────────────────────────────────────────


class TestListDependencies:
    def test_list(self, writer_client, task_a, task_b, task_c):
        TaskDependency.objects.create(predecessor=task_a, successor=task_b)
        TaskDependency.objects.create(predecessor=task_c, successor=task_b)

        resp = writer_client.get(f"/api/tasks/{task_b.id}/dependencies/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["predecessors"]) == 2
        assert len(data["successors"]) == 0

        resp2 = writer_client.get(f"/api/tasks/{task_a.id}/dependencies/")
        data2 = resp2.json()
        assert len(data2["predecessors"]) == 0
        assert len(data2["successors"]) == 1


# ── Обновление и удаление ────────────────────────────────────────────────


class TestUpdateDelete:
    def test_update(self, writer_client, task_a, task_b):
        dep = TaskDependency.objects.create(
            predecessor=task_a,
            successor=task_b,
        )
        resp = writer_client.put(
            f"/api/dependencies/{dep.id}/",
            json.dumps({"dep_type": "FF", "lag_days": 5}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        dep.refresh_from_db()
        assert dep.dep_type == "FF"
        assert dep.lag_days == 5

    def test_delete(self, writer_client, task_a, task_b):
        dep = TaskDependency.objects.create(
            predecessor=task_a,
            successor=task_b,
        )
        resp = writer_client.delete(f"/api/dependencies/{dep.id}/")
        assert resp.status_code == 200
        assert not TaskDependency.objects.filter(pk=dep.id).exists()


# ── Выравнивание дат ─────────────────────────────────────────────────────


class TestAlignDates:
    def test_align_fs(self, writer_client, task_a, task_b):
        """FS: дата начала B = дата окончания A + lag."""
        TaskDependency.objects.create(
            predecessor=task_a,
            successor=task_b,
            dep_type="FS",
            lag_days=2,
        )
        resp = writer_client.post(
            f"/api/tasks/{task_b.id}/align_dates/",
            json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        task_b.refresh_from_db()
        # A ends 2026-01-10 (сб), lag=2 раб.дня → пн 12 (1) + вт 13 (2) → B starts 2026-01-13
        assert task_b.date_start == date(2026, 1, 13)

    def test_align_preserves_duration(self, writer_client, task_a, task_b):
        """Длительность задачи должна сохраняться при выравнивании."""
        TaskDependency.objects.create(
            predecessor=task_a,
            successor=task_b,
            dep_type="FS",
            lag_days=0,
        )
        old_duration = (task_b.date_end - task_b.date_start).days  # 10 дней

        resp = writer_client.post(
            f"/api/tasks/{task_b.id}/align_dates/",
            json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        task_b.refresh_from_db()
        assert task_b.date_start == date(2026, 1, 10)
        assert (task_b.date_end - task_b.date_start).days == old_duration

    def test_align_pp_rejected(self, writer_client, pp_task, task_a):
        """PP-only задачи нельзя выравнивать."""
        TaskDependency.objects.create(
            predecessor=task_a,
            successor=pp_task,
        )
        resp = writer_client.post(
            f"/api/tasks/{pp_task.id}/align_dates/",
            json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400


# ── Все зависимости (для Ганта) ──────────────────────────────────────────


class TestAllDependencies:
    def test_all_deps(self, writer_client, task_a, task_b, task_c):
        TaskDependency.objects.create(predecessor=task_a, successor=task_b)
        TaskDependency.objects.create(predecessor=task_b, successor=task_c)

        resp = writer_client.get("/api/dependencies/?context=plan")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["source"] == task_a.id
        assert data[0]["target"] == task_b.id


# ── predecessors_count в сериализации ─────────────────────────────────────


class TestPredecessorsCount:
    def test_tasks_api_returns_count(self, writer_client, task_a, task_b):
        TaskDependency.objects.create(predecessor=task_a, successor=task_b)
        resp = writer_client.get("/api/tasks/")
        assert resp.status_code == 200
        data = resp.json()
        counts = {t["id"]: t["predecessors_count"] for t in data}
        assert counts[task_b.id] == 1
        assert counts[task_a.id] == 0
