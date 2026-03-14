"""
Тесты API производственного плана (/api/production_plan/).
Проверяют фильтрацию по ролям, создание, inline-обновление и удаление записей ПП.
"""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.employees.models import Employee, Department
from apps.works.models import Work, PPProject, Directory

User = get_user_model()


# ── Дополнительные фикстуры ──────────────────────────────────────────────────

@pytest.fixture
def dept_other(db):
    """Второй отдел — для тестов видимости."""
    return Department.objects.create(code='202', name='Чужой отдел')


@pytest.fixture
def dept_head_other(db, dept_other):
    """Начальник чужого отдела — не должен видеть записи первого."""
    user = User.objects.create_user(username='other_head', password='testpass123')
    Employee.objects.create(
        user=user,
        last_name='Козлов',
        first_name='Андрей',
        patronymic='Викторович',
        role=Employee.ROLE_DEPT_HEAD,
        department=dept_other,
    )
    return user


@pytest.fixture
def pp_project(db):
    """Проект ПП для привязки записей."""
    return PPProject.objects.create(name='Тестовый план ПП')


@pytest.fixture
def task_type_dir(db):
    """Запись справочника task_type — нужна для валидации."""
    return Directory.objects.create(dir_type='task_type', value='Выпуск нового документа')


@pytest.fixture
def pp_work_dept1(db, dept, pp_project):
    """Запись ПП, привязанная к первому отделу."""
    return Work.objects.create(
        show_in_pp=True,
        work_name='ПП-запись отдел 101',
        department=dept,
        pp_project=pp_project,
    )


@pytest.fixture
def pp_work_dept2(db, dept_other, pp_project):
    """Запись ПП, привязанная ко второму отделу."""
    return Work.objects.create(
        show_in_pp=True,
        work_name='ПП-запись отдел 202',
        department=dept_other,
        pp_project=pp_project,
    )


# ── Видимость (фильтрация по ролям) ──────────────────────────────────────────

@pytest.mark.django_db
class TestProductionPlanVisibility:
    def test_admin_sees_all(self, admin_user, pp_work_dept1, pp_work_dept2):
        client = Client()
        client.force_login(admin_user)
        resp = client.get('/api/production_plan/')
        assert resp.status_code == 200
        data = resp.json()
        ids = {w['id'] for w in data}
        # Админ видит записи обоих отделов
        assert pp_work_dept1.id in ids
        assert pp_work_dept2.id in ids

    def test_dept_head_sees_all_depts(
        self, dept_head_user, pp_work_dept1, pp_work_dept2,
    ):
        """ПП — общий документ, виден всем авторизованным."""
        client = Client()
        client.force_login(dept_head_user)
        resp = client.get('/api/production_plan/')
        assert resp.status_code == 200
        data = resp.json()
        ids = {w['id'] for w in data}
        assert pp_work_dept1.id in ids
        assert pp_work_dept2.id in ids

    def test_regular_user_sees_all_depts(
        self, regular_user, pp_work_dept1, pp_work_dept2,
    ):
        """ПП — общий документ, виден всем авторизованным."""
        client = Client()
        client.force_login(regular_user)
        resp = client.get('/api/production_plan/')
        assert resp.status_code == 200
        data = resp.json()
        ids = {w['id'] for w in data}
        assert pp_work_dept1.id in ids
        assert pp_work_dept2.id in ids

    def test_other_dept_head_sees_all_depts(
        self, dept_head_other, pp_work_dept1, pp_work_dept2,
    ):
        """ПП — общий документ, виден всем авторизованным."""
        client = Client()
        client.force_login(dept_head_other)
        resp = client.get('/api/production_plan/')
        assert resp.status_code == 200
        data = resp.json()
        ids = {w['id'] for w in data}
        assert pp_work_dept1.id in ids
        assert pp_work_dept2.id in ids


# ── Создание записей ПП ──────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProductionPlanCreate:
    def test_create_requires_project_id(self, admin_user, task_type_dir):
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            '/api/production_plan/create/',
            data=json.dumps({'work_name': 'Новая работа'}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert 'проект' in resp.json()['error'].lower()

    def test_create_ok_admin(self, admin_user, pp_project, task_type_dir):
        client = Client()
        client.force_login(admin_user)
        resp = client.post(
            '/api/production_plan/create/',
            data=json.dumps({
                'project_id': pp_project.id,
                'work_name': 'Выпуск документации КД',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 'id' in data
        # Запись должна существовать в БД
        assert Work.objects.filter(pk=data['id'], show_in_pp=True).exists()

    def test_dept_head_restricted_to_own_dept(
        self, dept_head_user, dept, dept_other, pp_project, task_type_dir,
    ):
        """Начальник отдела не может создать запись для чужого отдела."""
        client = Client()
        client.force_login(dept_head_user)
        resp = client.post(
            '/api/production_plan/create/',
            data=json.dumps({
                'project_id': pp_project.id,
                'work_name': 'Работа для чужого отдела',
                'dept': dept_other.code,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_regular_user_cannot_create(self, regular_user, pp_project, task_type_dir):
        """Обычный пользователь не может создавать записи ПП (не writer)."""
        client = Client()
        client.force_login(regular_user)
        resp = client.post(
            '/api/production_plan/create/',
            data=json.dumps({
                'project_id': pp_project.id,
                'work_name': 'Тестовая работа',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 403


# ── Inline-обновление ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProductionPlanUpdate:
    def test_inline_update_work_name(self, admin_user, pp_work_dept1):
        client = Client()
        client.force_login(admin_user)
        resp = client.put(
            f'/api/production_plan/{pp_work_dept1.id}/?field=work_name',
            data=json.dumps({'value': 'Обновлённое название'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        pp_work_dept1.refresh_from_db()
        assert pp_work_dept1.work_name == 'Обновлённое название'

    def test_inline_update_disallowed_field(self, admin_user, pp_work_dept1):
        """Поля, не входящие в PRODUCTION_ALLOWED_FIELDS, отклоняются."""
        client = Client()
        client.force_login(admin_user)
        resp = client.put(
            f'/api/production_plan/{pp_work_dept1.id}/?field=show_in_pp',
            data=json.dumps({'value': False}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_update_nonexistent_returns_404(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        resp = client.put(
            '/api/production_plan/999999/?field=work_name',
            data=json.dumps({'value': 'test'}),
            content_type='application/json',
        )
        assert resp.status_code == 404


# ── Удаление ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProductionPlanDelete:
    def test_delete_pp_only_hard_deletes(self, admin_user, pp_project, dept):
        """Запись только в ПП (show_in_plan=False) — полностью удаляется."""
        work = Work.objects.create(
            show_in_pp=True, show_in_plan=False,
            work_name='Только ПП', department=dept,
            pp_project=pp_project,
        )
        work_id = work.id
        client = Client()
        client.force_login(admin_user)
        resp = client.delete(f'/api/production_plan/{work_id}/')
        assert resp.status_code == 200
        assert not Work.objects.filter(pk=work_id).exists()

    def test_delete_pp_and_plan_hides_from_pp(self, admin_user, pp_project, dept):
        """Запись видна и в ПП и в СП — убирается из ПП, остаётся в СП."""
        work = Work.objects.create(
            show_in_pp=True, show_in_plan=True,
            work_name='В обоих модулях', department=dept,
            pp_project=pp_project,
        )
        work_id = work.id
        client = Client()
        client.force_login(admin_user)
        resp = client.delete(f'/api/production_plan/{work_id}/')
        assert resp.status_code == 200
        # Запись должна остаться в БД, но show_in_pp=False
        work.refresh_from_db()
        assert work.show_in_pp is False
        assert work.show_in_plan is True

    def test_delete_other_dept_forbidden(
        self, dept_head_user, dept_other, pp_project,
    ):
        """Начальник отдела не может удалить запись чужого отдела."""
        work = Work.objects.create(
            show_in_pp=True, show_in_plan=False,
            work_name='Чужая запись', department=dept_other,
            pp_project=pp_project,
        )
        client = Client()
        client.force_login(dept_head_user)
        resp = client.delete(f'/api/production_plan/{work.id}/')
        assert resp.status_code == 403
