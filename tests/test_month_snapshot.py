"""
Тесты /api/analytics/month_snapshot/ — снимок месяца.

Покрытие:
  • Шесть статусов (done/done_early/overdue/inwork/debt_closed/debt_hanging)
  • Правило приоритета: долг всегда в группе «Долги»,
    даже если есть план-часы на выбранный месяц
  • Фильтр по отделу/сектору/центру/проекту
  • Валидация параметра month
  • Доступ: anon = 401
  • Исторический снимок: отчёт, сданный ПОСЛЕ месяца,
    оставляет задачу в «Просрочено» этого месяца
"""

from datetime import date, datetime

import pytest
from django.test import Client
from django.utils import timezone

from apps.works.models import Work, WorkReport


def _dt(year, month, day):
    """Aware datetime для created_at отчёта."""
    naive = datetime(year, month, day, 12, 0, 0)
    return timezone.make_aware(naive)


@pytest.fixture
def w_done_in_march(db, dept):
    """Дедлайн в марте, отчёт в марте → done."""
    w = Work.objects.create(
        work_name="done-march",
        show_in_plan=True,
        department=dept,
        date_end=date(2026, 3, 20),
        plan_hours={"2026-03": 40},
    )
    r = WorkReport.objects.create(work=w, doc_name="r")
    WorkReport.objects.filter(pk=r.pk).update(created_at=_dt(2026, 3, 20))
    return w


@pytest.fixture
def w_done_early(db, dept):
    """Дедлайн в апреле, отчёт в марте, план-часы в марте → done_early."""
    w = Work.objects.create(
        work_name="done-early",
        show_in_plan=True,
        department=dept,
        date_end=date(2026, 4, 15),
        plan_hours={"2026-03": 20, "2026-04": 20},
    )
    r = WorkReport.objects.create(work=w, doc_name="r")
    WorkReport.objects.filter(pk=r.pk).update(created_at=_dt(2026, 3, 25))
    return w


@pytest.fixture
def w_overdue(db, dept):
    """Дедлайн в марте, отчёта нет → overdue."""
    return Work.objects.create(
        work_name="overdue",
        show_in_plan=True,
        department=dept,
        date_end=date(2026, 3, 25),
        plan_hours={"2026-03": 30},
    )


@pytest.fixture
def w_inwork(db, dept):
    """Дедлайн в апреле, отчёта нет, план-часы в марте → inwork."""
    return Work.objects.create(
        work_name="inwork",
        show_in_plan=True,
        department=dept,
        date_end=date(2026, 4, 10),
        plan_hours={"2026-03": 15, "2026-04": 15},
    )


@pytest.fixture
def w_debt_hanging(db, dept):
    """Дедлайн в феврале, отчёта нет совсем → debt_hanging."""
    return Work.objects.create(
        work_name="debt-hanging",
        show_in_plan=True,
        department=dept,
        date_end=date(2026, 2, 20),
        plan_hours={},
    )


@pytest.fixture
def w_debt_closed(db, dept):
    """Дедлайн в январе, отчёт сдан в марте → debt_closed."""
    w = Work.objects.create(
        work_name="debt-closed",
        show_in_plan=True,
        department=dept,
        date_end=date(2026, 1, 30),
        plan_hours={},
    )
    r = WorkReport.objects.create(work=w, doc_name="r")
    WorkReport.objects.filter(pk=r.pk).update(created_at=_dt(2026, 3, 10))
    return w


@pytest.fixture
def w_debt_with_march_plan(db, dept):
    """
    Дедлайн в феврале, отчёта нет, НО план-часы на март стоят.
    По правилу #7 — всё равно долг (не «задача месяца»).
    """
    return Work.objects.create(
        work_name="debt-but-planned",
        show_in_plan=True,
        department=dept,
        date_end=date(2026, 2, 10),
        plan_hours={"2026-03": 10},
    )


# ── Доступ ────────────────────────────────────────────────────────────────


class TestAccess:
    def test_anon_401(self):
        c = Client()
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        assert r.status_code == 401

    def test_bad_month_400(self, admin_user):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-99")
        assert r.status_code == 400

    def test_missing_month_400(self, admin_user):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/")
        assert r.status_code == 400


# ── Шесть категорий ──────────────────────────────────────────────────────


class TestCategories:
    def test_done(self, admin_user, w_done_in_march):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["month_tasks"]["done"] == 1
        assert data["month_tasks"]["total"] == 1
        assert data["debts"]["total"] == 0

    def test_done_early(self, admin_user, w_done_early):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["month_tasks"]["done_early"] == 1
        assert data["month_tasks"]["done"] == 0

    def test_overdue(self, admin_user, w_overdue):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["month_tasks"]["overdue"] == 1
        assert data["month_tasks"]["closed"] == 0

    def test_inwork(self, admin_user, w_inwork):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["month_tasks"]["inwork"] == 1

    def test_debt_hanging(self, admin_user, w_debt_hanging):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["debts"]["hanging"] == 1
        assert data["debts"]["closed"] == 0
        assert data["month_tasks"]["total"] == 0

    def test_debt_closed(self, admin_user, w_debt_closed):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["debts"]["closed"] == 1
        assert data["debts"]["hanging"] == 0


# ── Главное правило приоритета ──────────────────────────────────────────


class TestDebtPriority:
    def test_debt_with_march_plan_still_debt(self, admin_user, w_debt_with_march_plan):
        """
        Задача с дедлайном в феврале и план-часами в марте —
        должна попасть в «Долги», а не в «Задачи месяца».
        """
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["debts"]["total"] == 1
        assert data["debts"]["hanging"] == 1
        assert data["month_tasks"]["total"] == 0


# ── Исторический снимок ─────────────────────────────────────────────────


class TestHistoricalSnapshot:
    def test_future_deadline_in_current_month_is_inwork(
        self, admin_user, dept, monkeypatch
    ):
        """
        Текущий месяц ещё не закончился: задача с дедлайном в будущем
        (после сегодня, но в этом же месяце) должна быть «в работе»,
        а не «просрочена».
        """
        # Фиксируем «сегодня» = 10 марта 2026 (середина месяца)
        import apps.api.views.month_snapshot as ms

        class _FakeTZ:
            @staticmethod
            def now():
                return datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)

        monkeypatch.setattr(ms, "timezone", _FakeTZ)

        # Дедлайн 25 марта — в будущем относительно 10 марта
        Work.objects.create(
            work_name="future-in-month",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 3, 25),
            plan_hours={"2026-03": 40},
        )
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["month_tasks"]["inwork"] == 1
        assert data["month_tasks"]["overdue"] == 0

    def test_past_deadline_in_current_month_is_overdue(
        self, admin_user, dept, monkeypatch
    ):
        """
        Текущий месяц: дедлайн в прошлом (до сегодня) и отчёта нет →
        «просрочено». Это проверка, что фикс не сломал базовое поведение.
        """
        import apps.api.views.month_snapshot as ms

        class _FakeTZ:
            @staticmethod
            def now():
                return datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)

        monkeypatch.setattr(ms, "timezone", _FakeTZ)

        Work.objects.create(
            work_name="past-in-month",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 3, 10),
            plan_hours={"2026-03": 40},
        )
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["month_tasks"]["overdue"] == 1
        assert data["month_tasks"]["inwork"] == 0

    def test_past_month_all_overdue_regardless_of_today(
        self, admin_user, dept, monkeypatch
    ):
        """
        Прошедший месяц: сегодня уже в апреле, смотрим снимок марта.
        Все мартовские задачи без отчёта — «просрочено», today не важна.
        """
        import apps.api.views.month_snapshot as ms

        class _FakeTZ:
            @staticmethod
            def now():
                return datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)

        monkeypatch.setattr(ms, "timezone", _FakeTZ)

        Work.objects.create(
            work_name="march-no-report",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 3, 28),
            plan_hours={"2026-03": 40},
        )
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["month_tasks"]["overdue"] == 1

    def test_report_in_april_stays_overdue_in_march(self, admin_user, dept):
        """
        Задача с дедлайном в марте, отчёт сдан в апреле.
        Смотрим снимок марта — должна остаться в «Просрочено», а не исчезнуть.
        """
        w = Work.objects.create(
            work_name="late-report",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 3, 20),
            plan_hours={"2026-03": 40},
        )
        r = WorkReport.objects.create(work=w, doc_name="r")
        WorkReport.objects.filter(pk=r.pk).update(created_at=_dt(2026, 4, 5))

        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["month_tasks"]["overdue"] == 1
        assert data["month_tasks"]["done"] == 0


# ── Фильтры ──────────────────────────────────────────────────────────────


class TestFilters:
    def test_dept_filter(self, admin_user, dept, db):
        """Фильтр по коду отдела исключает задачи других отделов."""
        from apps.employees.models import Department

        other_dept = Department.objects.create(code="999", name="Другой")
        Work.objects.create(
            work_name="in-our-dept",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 3, 20),
            plan_hours={"2026-03": 10},
        )
        Work.objects.create(
            work_name="in-other-dept",
            show_in_plan=True,
            department=other_dept,
            date_end=date(2026, 3, 20),
            plan_hours={"2026-03": 10},
        )

        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get(f"/api/analytics/month_snapshot/?month=2026-03&dept={dept.code}")
        data = r.json()
        assert data["month_tasks"]["total"] == 1
        assert data["month_tasks"]["overdue"] == 1
        assert data["filters"]["dept"] == dept.code


# ── Полная смесь и проценты ──────────────────────────────────────────────


class TestSummary:
    def test_mixed_scene(
        self,
        admin_user,
        w_done_in_march,
        w_done_early,
        w_overdue,
        w_inwork,
        w_debt_hanging,
        w_debt_closed,
        w_debt_with_march_plan,
    ):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()

        mt = data["month_tasks"]
        assert mt["done"] == 1
        assert mt["done_early"] == 1
        assert mt["overdue"] == 1
        assert mt["inwork"] == 1
        assert mt["total"] == 4
        assert mt["closed"] == 2
        assert mt["closed_pct"] == 50.0

        d = data["debts"]
        assert d["closed"] == 1
        # Два долга: w_debt_hanging + w_debt_with_march_plan
        assert d["hanging"] == 2
        assert d["total"] == 3

    def test_task_ids_returned(self, admin_user, w_overdue):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert w_overdue.id in data["month_tasks"]["task_ids"]["overdue"]


# ── Scope по роли (стартовый экран) ──────────────────────────────────────


class TestRoleScope:
    """
    Снимок без явных фильтров должен показывать те же задачи, что и
    стартовый экран пользователя в СП/Аналитике: dept_head → свой отдел.
    Без этого начальник отдела видел задачи ВСЕХ отделов (баг).
    """

    def test_dept_head_without_filter_sees_only_own_dept(
        self, dept_head_user, dept, db
    ):
        from apps.employees.models import Department

        other_dept = Department.objects.create(code="999", name="Другой")
        # Задача в своём отделе — должна попасть в снимок
        Work.objects.create(
            work_name="ours",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 3, 20),
            plan_hours={"2026-03": 10},
        )
        # Задача в чужом отделе — не должна попасть
        Work.objects.create(
            work_name="theirs",
            show_in_plan=True,
            department=other_dept,
            date_end=date(2026, 3, 20),
            plan_hours={"2026-03": 10},
        )

        c = Client()
        c.login(username="dept_head_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        # Только одна задача — из своего отдела
        assert data["month_tasks"]["total"] == 1
        # Фильтр dept автоматически подставился
        assert data["filters"]["dept"] == dept.code

    def test_explicit_dept_filter_overrides_role_scope(self, dept_head_user, dept, db):
        """Если клиент явно передал dept — автоподстановка не срабатывает."""
        from apps.employees.models import Department

        other_dept = Department.objects.create(code="999", name="Другой")
        Work.objects.create(
            work_name="theirs",
            show_in_plan=True,
            department=other_dept,
            date_end=date(2026, 3, 20),
            plan_hours={"2026-03": 10},
        )

        c = Client()
        c.login(username="dept_head_test", password="testpass123")
        r = c.get(
            f"/api/analytics/month_snapshot/?month=2026-03&dept={other_dept.code}"
        )
        data = r.json()
        # Пользователь явно запросил другой отдел — показываем его
        assert data["month_tasks"]["total"] == 1
        assert data["filters"]["dept"] == other_dept.code

    def test_admin_without_filter_sees_all(self, admin_user, dept, db):
        """Админ без фильтра — видит задачи всех отделов."""
        from apps.employees.models import Department

        other_dept = Department.objects.create(code="999", name="Другой")
        Work.objects.create(
            work_name="ours",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 3, 20),
            plan_hours={"2026-03": 10},
        )
        Work.objects.create(
            work_name="theirs",
            show_in_plan=True,
            department=other_dept,
            date_end=date(2026, 3, 20),
            plan_hours={"2026-03": 10},
        )
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert data["month_tasks"]["total"] == 2
        assert data["filters"]["dept"] is None


# ── Блок «hours» — план/долг/норма в часах ───────────────────────────────


class TestHoursBlock:
    """Проверяем новые поля: planned_hours, debt_hours, norm_hours, load_*_pct."""

    def test_hours_block_structure(self, admin_user, w_done_in_march):
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03")
        data = r.json()
        assert "hours" in data
        h = data["hours"]
        for k in (
            "planned",
            "debt",
            "total",
            "norm_per_employee",
            "staff_count",
            "norm",
            "load_plan_pct",
            "load_total_pct",
        ):
            assert k in h, f"Нет поля {k} в hours"

    def test_planned_hours_sum(self, admin_user, dept, db):
        """Сумма plan_hours на текущий месяц по задачам месяца."""
        # Задача месяца с 40 часами на март
        Work.objects.create(
            work_name="w1",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 3, 20),
            plan_hours={"2026-03": 40},
        )
        # Задача месяца с 25 часами на март
        Work.objects.create(
            work_name="w2",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 3, 28),
            plan_hours={"2026-03": 25},
        )
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03&dept=" + dept.code)
        data = r.json()
        assert data["hours"]["planned"] == 65.0
        assert data["hours"]["debt"] == 0.0

    def test_debt_hours_from_last_past_plan(self, admin_user, dept, db):
        """
        Для долга без часов на текущий месяц — берётся последний план
        из прошлого (fallback).
        """
        # Долг: дедлайн в феврале, часы только на февраль
        Work.objects.create(
            work_name="debt-feb",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 2, 20),
            plan_hours={"2026-02": 32},
        )
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03&dept=" + dept.code)
        data = r.json()
        assert data["debts"]["hanging"] == 1
        assert data["hours"]["debt"] == 32.0  # взяли февральский план
        assert data["hours"]["planned"] == 0.0

    def test_debt_hours_prefers_current_month_if_set(self, admin_user, dept, db):
        """Если у долга есть часы на текущий месяц — берём их, а не прошлые."""
        Work.objects.create(
            work_name="debt-replan",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 2, 20),
            plan_hours={"2026-02": 32, "2026-03": 10},
        )
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03&dept=" + dept.code)
        data = r.json()
        assert data["debts"]["hanging"] == 1
        assert data["hours"]["debt"] == 10.0  # именно мартовский, не февральский

    def test_norm_and_load(self, admin_user, dept, db):
        """
        Норма = hours_norm × staff_count. Загрузка — по плану и с долгом.
        """
        from apps.works.models import WorkCalendar

        WorkCalendar.objects.update_or_create(
            year=2026, month=3, defaults={"hours_norm": 160}
        )
        # Один сотрудник в этом отделе — норма = 160
        from django.contrib.auth.models import User

        from apps.employees.models import Employee

        u = User.objects.create_user(username="emp_for_norm", password="testpass123")
        Employee.objects.create(
            user=u,
            last_name="Т",
            first_name="Т",
            department=dept,
            is_active=True,
        )
        Work.objects.create(
            work_name="plan-task",
            show_in_plan=True,
            department=dept,
            date_end=date(2026, 3, 20),
            plan_hours={"2026-03": 80},
        )
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2026-03&dept=" + dept.code)
        data = r.json()
        assert data["hours"]["norm_per_employee"] == 160.0
        assert data["hours"]["staff_count"] >= 1
        assert data["hours"]["norm"] >= 160.0
        # Загрузка по плану = 80 / norm
        assert data["hours"]["load_plan_pct"] > 0

    def test_no_calendar_entry_means_zero_norm(self, admin_user, dept, db):
        """
        Если в производственном календаре на этот месяц нет записи —
        norm = 0, load_* = 0. Фронт должен корректно обработать.
        """
        from apps.works.models import WorkCalendar

        WorkCalendar.objects.filter(year=2099, month=1).delete()
        c = Client()
        c.login(username="admin_test", password="testpass123")
        r = c.get("/api/analytics/month_snapshot/?month=2099-01")
        data = r.json()
        assert data["hours"]["norm_per_employee"] == 0.0
        assert data["hours"]["norm"] == 0.0
        assert data["hours"]["load_plan_pct"] == 0.0
        assert data["hours"]["load_total_pct"] == 0.0
