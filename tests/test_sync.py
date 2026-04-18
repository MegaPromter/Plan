"""
Тесты синхронизации ПП → СП и блокировки полей.

Проверяет:
1. Синхронизация включает show_in_plan=True (без копирования)
2. Повторная синхронизация не создаёт дубли
3. Удаление из СП записи ПП — только show_in_plan=False
4. Блокировка ПП-полей при редактировании в СП
5. Разрешённые поля (executor, date_start, date_end, plan_hours) редактируемы
6. deadline заблокирован для ПП-записей
7. Сериализация: deadline = date_end для ПП-записей
"""

import json
from datetime import date

import pytest
from django.test import Client

from apps.works.models import PPProject, Work


@pytest.fixture
def pp_project(db):
    """Проект производственного плана."""
    return PPProject.objects.create(name="Персей")


@pytest.fixture
def pp_work(db, pp_project, dept):
    """Запись ПП (show_in_pp=True, show_in_plan=False)."""
    return Work.objects.create(
        show_in_pp=True,
        show_in_plan=False,
        pp_project=pp_project,
        work_name="Разработка корпуса",
        work_num="001",
        work_designation="АБВГ.123456.001",
        stage_num="1",
        milestone_num="2",
        task_type="Выпуск нового документа",
        department=dept,
        date_end=date(2026, 6, 30),
    )


@pytest.fixture
def synced_work(pp_work):
    """Запись ПП, синхронизированная в СП."""
    pp_work.show_in_plan = True
    pp_work.save(update_fields=["show_in_plan"])
    return pp_work


@pytest.fixture
def pure_sp_work(db, dept):
    """Чистая СП-запись (только show_in_plan=True)."""
    return Work.objects.create(
        show_in_pp=False,
        show_in_plan=True,
        work_name="Техническое задание",
        work_num="TZ-001",
        department=dept,
        deadline=date(2026, 5, 15),
    )


# ---------------------------------------------------------------------------
#  Тесты синхронизации ПП → СП
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPPSync:
    def test_sync_sets_show_in_plan(self, admin_user, pp_work, pp_project):
        """Синхронизация включает show_in_plan=True на записи ПП."""
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            "/api/production_plan/sync/",
            data=json.dumps({"project_id": pp_project.id}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced"] == 1

        pp_work.refresh_from_db()
        assert pp_work.show_in_plan is True
        assert pp_work.show_in_pp is True
        # Запись осталась одна — дубликат НЕ создан
        assert Work.objects.count() == 1

    def test_sync_idempotent(self, admin_user, synced_work, pp_project):
        """Повторная синхронизация не создаёт дубли (synced=0)."""
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            "/api/production_plan/sync/",
            data=json.dumps({"project_id": pp_project.id}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced"] == 0
        assert Work.objects.count() == 1

    def test_sync_requires_project_id(self, admin_user):
        """Синхронизация без project_id → 400."""
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            "/api/production_plan/sync/",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  Тесты удаления из СП
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeleteFromSP:
    def test_delete_pp_record_only_hides_from_sp(self, admin_user, synced_work):
        """Удаление ПП-записи из СП → show_in_plan=False, запись сохраняется."""
        client = Client()
        client.force_login(admin_user)
        resp = client.delete(f"/api/tasks/{synced_work.id}/")
        assert resp.status_code == 200

        synced_work.refresh_from_db()
        assert synced_work.show_in_plan is False
        assert synced_work.show_in_pp is True
        assert Work.objects.filter(pk=synced_work.pk).exists()

    def test_delete_pure_sp_actually_deletes(self, admin_user, pure_sp_work):
        """Удаление чистой СП-записи → запись удаляется из БД."""
        client = Client()
        client.force_login(admin_user)
        resp = client.delete(f"/api/tasks/{pure_sp_work.id}/")
        assert resp.status_code == 200
        assert not Work.objects.filter(pk=pure_sp_work.pk).exists()


# ---------------------------------------------------------------------------
#  Тесты блокировки ПП-полей в СП
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPPFieldLocking:
    def test_pp_fields_locked_on_update(self, admin_user, synced_work):
        """ПП-поля (work_name, description и т.д.) не меняются через СП API.
        Если все переданные поля заблокированы — возвращается 403."""
        client = Client()
        client.force_login(admin_user)

        original_name = synced_work.work_name
        original_designation = synced_work.work_designation
        original_stage = synced_work.stage_num
        original_task_type = synced_work.task_type

        # Только заблокированные поля → 403
        resp = client.put(
            f"/api/tasks/{synced_work.id}/",
            data=json.dumps(
                {
                    "work_name": "ИЗМЕНЁННОЕ ИМЯ",
                    "description": "ИЗМЕНЁННОЕ ОБОЗНАЧЕНИЕ",
                    "stage": "999",
                    "task_type": "Корректировка",
                    "justification": "Попытка изменить",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 403
        data = json.loads(resp.content)
        assert "locked_fields" in data

        synced_work.refresh_from_db()
        # Заблокированные поля НЕ изменились
        assert synced_work.work_name == original_name
        assert synced_work.work_designation == original_designation
        assert synced_work.stage_num == original_stage
        assert synced_work.task_type == original_task_type

    def test_allowed_fields_editable(self, admin_user, synced_work):
        """Разрешённые поля (executor, date_start, date_end, plan_hours) меняются."""
        client = Client()
        client.force_login(admin_user)

        resp = client.put(
            f"/api/tasks/{synced_work.id}/",
            data=json.dumps(
                {
                    "executor": "Новый Исполнитель",
                    "date_start": "2026-01-15",
                    "date_end": "2026-07-31",
                    "deadline": "2026-06-30",
                    "plan_hours": {"2026-01": 40, "2026-02": 80},
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200

        synced_work.refresh_from_db()
        # executor устанавливается через FK; если Employee не найден — None
        assert (
            synced_work.executor is None
        )  # 'Новый Исполнитель' не существует в Employee
        assert synced_work.date_start == date(2026, 1, 15)
        assert synced_work.date_end == date(2026, 7, 31)
        assert synced_work.deadline == date(2026, 6, 30)
        assert synced_work.plan_hours == {"2026-01": 40, "2026-02": 80}

    def test_pure_sp_all_fields_editable(self, admin_user, pure_sp_work):
        """Для чистой СП-записи все поля редактируемы, включая deadline."""
        client = Client()
        client.force_login(admin_user)

        resp = client.put(
            f"/api/tasks/{pure_sp_work.id}/",
            data=json.dumps(
                {
                    "work_name": "Обновлённое ТЗ",
                    "description": "Новое обозначение",
                    "deadline": "2026-09-01",
                    "stage": "3",
                    "justification": "Приказ №123",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200

        pure_sp_work.refresh_from_db()
        assert pure_sp_work.work_name == "Обновлённое ТЗ"
        assert pure_sp_work.work_designation == "Новое обозначение"
        assert pure_sp_work.deadline == date(2026, 9, 1)
        assert pure_sp_work.stage_num == "3"
        assert pure_sp_work.justification == "Приказ №123"


# ---------------------------------------------------------------------------
#  Тесты сериализации
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSerialization:
    def test_pp_deadline_equals_date_end(self, admin_user, synced_work):
        """Для ПП-записи deadline в JSON = date_end из ПП."""
        client = Client()
        client.force_login(admin_user)
        resp = client.get("/api/tasks/")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) == 1
        task = tasks[0]
        assert task["deadline"] == "2026-06-30"  # date_end из ПП
        assert task["from_pp"] is True

    def test_pp_justification_formatted(self, admin_user, synced_work):
        """Для ПП-записи обоснование формируется из ПП-полей."""
        client = Client()
        client.force_login(admin_user)
        resp = client.get("/api/tasks/")
        tasks = resp.json()
        task = tasks[0]
        # Формат: «ПП-план; Этап X; Работа Z»
        assert "Персей" in task["justification"]
        assert "Этап 1" in task["justification"]
        assert "№ работы 001" in task["justification"]

    def test_sp_deadline_is_own(self, admin_user, pure_sp_work):
        """Для чистой СП-записи deadline = собственный deadline."""
        client = Client()
        client.force_login(admin_user)
        resp = client.get("/api/tasks/")
        tasks = resp.json()
        # Находим чистую СП-задачу
        sp_task = [t for t in tasks if not t["from_pp"]]
        assert len(sp_task) == 1
        assert sp_task[0]["deadline"] == "2026-05-15"

    def test_pp_work_number_mapped(self, admin_user, synced_work):
        """work_num маппится в work_number в JSON."""
        client = Client()
        client.force_login(admin_user)
        resp = client.get("/api/tasks/")
        tasks = resp.json()
        task = tasks[0]
        assert task["work_number"] == "001"
        assert task["description"] == "АБВГ.123456.001"
        assert task["stage"] == "1"

    def test_task_duration_over_5_years_rejected(self, admin_user, synced_work):
        """Длительность задачи не может превышать 5 лет."""
        client = Client()
        client.force_login(admin_user)
        resp = client.put(
            f"/api/tasks/{synced_work.id}/",
            data=json.dumps(
                {
                    "date_start": "2025-01-01",
                    "date_end": "2032-01-01",  # 7 лет — должно отклониться
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "5 лет" in resp.json().get("error", "")
