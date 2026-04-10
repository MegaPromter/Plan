"""
Тесты на фиксы безопасности и качества:
- Comments: visibility filter, пагинация (лимит 200), аудит-лог удаления
- Feedback: видимость (admin vs user), валидация файлов (тип, размер)
- Enterprise: кросс-проектная валидация зависимостей ГГ
- Rate limiting: 10 попыток логина
"""

import json

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.employees.models import Department, Employee
from apps.works.models import AuditLog, Feedback, Work, WorkComment

# ── Фикстуры ──────────────────────────────────────────────────────────────


@pytest.fixture
def dept(db):
    return Department.objects.create(code="101", name="Отдел 101")


@pytest.fixture
def dept2(db):
    return Department.objects.create(code="202", name="Отдел 202")


@pytest.fixture
def admin_client(db, dept):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="adm", password="pass123pass")
    Employee.objects.create(user=user, last_name="Админ", role="admin", department=dept)
    c = Client()
    c.login(username="adm", password="pass123pass")
    return c


@pytest.fixture
def admin_user_obj(db, dept):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="adm2", password="pass123pass")
    Employee.objects.create(
        user=user, last_name="Админ2", role="admin", department=dept
    )
    return user


@pytest.fixture
def user_client(db, dept):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="usr", password="pass123pass")
    Employee.objects.create(user=user, last_name="Юзер", role="user", department=dept)
    c = Client()
    c.login(username="usr", password="pass123pass")
    return c


@pytest.fixture
def user2_client(db, dept2):
    """Пользователь из другого отдела."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="usr2", password="pass123pass")
    Employee.objects.create(
        user=user, last_name="Другой", role="user", department=dept2
    )
    c = Client()
    c.login(username="usr2", password="pass123pass")
    return c


@pytest.fixture
def work(db, dept):
    return Work.objects.create(
        work_name="Тестовая задача",
        show_in_plan=True,
        department=dept,
    )


@pytest.fixture
def work_dept2(db, dept2):
    return Work.objects.create(
        work_name="Задача отдела 202",
        show_in_plan=True,
        department=dept2,
    )


# ══════════════════════════════════════════════════════════════════════════
#  Comments: visibility filter
# ══════════════════════════════════════════════════════════════════════════


class TestCommentsVisibility:
    """Пользователь не должен видеть/создавать/удалять комментарии к чужим задачам."""

    def test_user_can_read_own_dept_comments(self, user_client, work):
        """Пользователь видит комментарии к задачам своего отдела."""
        WorkComment.objects.create(work=work, text="Тест")
        r = user_client.get(f"/api/comments/?work_id={work.pk}")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_user_cannot_read_other_dept_comments(self, user2_client, work):
        """Пользователь НЕ видит комментарии к задачам чужого отдела."""
        WorkComment.objects.create(work=work, text="Секрет")
        r = user2_client.get(f"/api/comments/?work_id={work.pk}")
        assert r.status_code == 404

    def test_user_cannot_create_comment_other_dept(self, user2_client, work):
        """Пользователь НЕ может создать комментарий к чужой задаче."""
        r = user2_client.post(
            "/api/comments/",
            json.dumps({"work_id": work.pk, "text": "Хак"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_user_cannot_delete_comment_other_dept(
        self, user2_client, work, admin_user_obj
    ):
        """Пользователь НЕ может удалить комментарий из чужого отдела."""
        comment = WorkComment.objects.create(
            work=work, author=admin_user_obj, text="Чужой"
        )
        r = user2_client.delete(f"/api/comments/{comment.pk}/")
        assert r.status_code == 404
        assert WorkComment.objects.filter(pk=comment.pk).exists()

    def test_admin_can_read_any_dept(self, admin_client, work_dept2):
        """Админ видит комментарии любого отдела."""
        WorkComment.objects.create(work=work_dept2, text="Любой")
        r = admin_client.get(f"/api/comments/?work_id={work_dept2.pk}")
        assert r.status_code == 200
        assert len(r.json()) == 1


# ══════════════════════════════════════════════════════════════════════════
#  Comments: пагинация (лимит 200)
# ══════════════════════════════════════════════════════════════════════════


class TestCommentsPagination:

    def test_comments_limited_to_200(self, admin_client, work, admin_user_obj):
        """API возвращает максимум 200 комментариев."""
        WorkComment.objects.bulk_create(
            [
                WorkComment(work=work, author=admin_user_obj, text=f"Комментарий {i}")
                for i in range(210)
            ]
        )
        r = admin_client.get(f"/api/comments/?work_id={work.pk}")
        assert r.status_code == 200
        assert len(r.json()) == 200


# ══════════════════════════════════════════════════════════════════════════
#  Comments: аудит-лог удаления
# ══════════════════════════════════════════════════════════════════════════


class TestCommentsAuditLog:

    def test_delete_creates_audit_log(self, admin_client, work, admin_user_obj):
        """Удаление комментария создаёт запись в AuditLog."""
        comment = WorkComment.objects.create(
            work=work, author=admin_user_obj, text="Удалить меня"
        )
        before = AuditLog.objects.count()
        r = admin_client.delete(f"/api/comments/{comment.pk}/")
        assert r.status_code == 200
        assert AuditLog.objects.count() == before + 1
        log = AuditLog.objects.latest("created_at")
        assert log.action == AuditLog.ACTION_COMMENT_DELETE
        assert log.object_id == comment.pk
        assert "work_id" in log.details


# ══════════════════════════════════════════════════════════════════════════
#  Feedback: видимость (admin видит всё, user — только свои)
# ══════════════════════════════════════════════════════════════════════════


class TestFeedbackVisibility:

    def _create_feedback(self, user, text="Тест"):
        return Feedback.objects.create(user=user, text=text, category="bug")

    def test_admin_sees_all_feedback(self, admin_client, admin_user_obj, db):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        other = User.objects.create_user(username="other", password="pass123pass")
        self._create_feedback(admin_user_obj, "Админское")
        self._create_feedback(other, "Чужое")
        r = admin_client.get("/api/feedback/")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_user_sees_only_own_feedback(self, user_client, admin_user_obj, db):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        # Получаем user объект из клиента
        usr = User.objects.get(username="usr")
        self._create_feedback(usr, "Моё")
        self._create_feedback(admin_user_obj, "Чужое")
        r = user_client.get("/api/feedback/")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["text"] == "Моё"


# ══════════════════════════════════════════════════════════════════════════
#  Feedback: валидация файлов
# ══════════════════════════════════════════════════════════════════════════


class TestFeedbackFileValidation:

    def test_rejects_oversized_file(self, user_client):
        """Файл > 5 МБ отклоняется."""
        big_file = SimpleUploadedFile(
            "big.png",
            b"\x89PNG" + b"\x00" * (6 * 1024 * 1024),
            content_type="image/png",
        )
        r = user_client.post(
            "/api/feedback/",
            {
                "text": "Баг",
                "category": "bug",
                "screenshot": big_file,
            },
        )
        assert r.status_code == 400
        assert "слишком большой" in r.json()["error"]

    def test_rejects_non_image_file(self, user_client):
        """Неизображения отклоняются."""
        exe_file = SimpleUploadedFile(
            "hack.exe",
            b"MZ\x00\x00",
            content_type="application/x-msdownload",
        )
        r = user_client.post(
            "/api/feedback/",
            {
                "text": "Баг",
                "category": "bug",
                "screenshot": exe_file,
            },
        )
        assert r.status_code == 400
        assert "изображения" in r.json()["error"]

    def test_accepts_valid_image(self, user_client):
        """Валидное изображение принимается."""
        # Минимальный 1x1 PNG
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
            b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        img = SimpleUploadedFile("ok.png", png_data, content_type="image/png")
        r = user_client.post(
            "/api/feedback/",
            {
                "text": "Баг",
                "category": "bug",
                "screenshot": img,
            },
        )
        assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════
#  Rate limiting: 10 попыток логина
# ══════════════════════════════════════════════════════════════════════════


class TestRateLimitLogin:

    def test_login_blocked_after_10_attempts(self, db):
        """После 10 неудачных логинов — 429."""
        cache.clear()
        c = Client()
        for i in range(10):
            c.post("/accounts/login/", {"username": "fake", "password": "wrong"})
        r = c.post("/accounts/login/", {"username": "fake", "password": "wrong"})
        assert r.status_code == 429

    def test_login_allowed_within_limit(self, db):
        """До 10 попыток — не блокирует."""
        cache.clear()
        c = Client()
        for i in range(9):
            r = c.post("/accounts/login/", {"username": "fake", "password": "wrong"})
            assert r.status_code != 429


# ══════════════════════════════════════════════════════════════════════════
#  Enterprise: кросс-проектная валидация зависимостей ГГ
# ══════════════════════════════════════════════════════════════════════════


class TestEnterpriseDependencyIsolation:

    @pytest.fixture
    def writer_client(self, db, dept):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="writer", password="pass123pass")
        Employee.objects.create(
            user=user, last_name="Писатель", role="dept_head", department=dept
        )
        c = Client()
        c.login(username="writer", password="pass123pass")
        return c

    @pytest.fixture
    def two_projects_with_stages(self, db):
        from apps.enterprise.models import GeneralSchedule, GGStage
        from apps.works.models import Project

        p1 = Project.objects.create(name_full="Проект 1")
        p2 = Project.objects.create(name_full="Проект 2")
        gg1 = GeneralSchedule.objects.create(project=p1)
        gg2 = GeneralSchedule.objects.create(project=p2)
        s1 = GGStage.objects.create(schedule=gg1, name="Этап P1")
        s2 = GGStage.objects.create(schedule=gg2, name="Этап P2")
        return s1, s2

    def test_cross_project_dependency_rejected(
        self, writer_client, two_projects_with_stages
    ):
        """Нельзя создать зависимость между этапами разных проектов."""
        s1, s2 = two_projects_with_stages
        r = writer_client.post(
            "/api/enterprise/gg_stage_deps/",
            json.dumps({"predecessor_id": s1.pk, "successor_id": s2.pk}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "одному" in r.json()["error"]

    def test_same_project_dependency_allowed(self, writer_client, db):
        """Зависимость между этапами одного проекта — ок."""
        from apps.enterprise.models import GeneralSchedule, GGStage
        from apps.works.models import Project

        p = Project.objects.create(name_full="Проект")
        gg = GeneralSchedule.objects.create(project=p)
        s1 = GGStage.objects.create(schedule=gg, name="Этап 1")
        s2 = GGStage.objects.create(schedule=gg, name="Этап 2")
        r = writer_client.post(
            "/api/enterprise/gg_stage_deps/",
            json.dumps({"predecessor_id": s1.pk, "successor_id": s2.pk}),
            content_type="application/json",
        )
        assert r.status_code == 201
