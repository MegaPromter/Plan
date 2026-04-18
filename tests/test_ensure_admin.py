"""
Тесты management-команды `ensure_admin`.

Проверяем что:
- команда создаёт суперпользователя с заданным логином/паролем;
- повторный запуск ничего не ломает (идемпотентность);
- флаг --reset меняет пароль у существующего пользователя;
- у пользователя появляется Employee с ролью admin.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.employees.models import Employee

User = get_user_model()


@pytest.mark.django_db
def test_creates_admin_when_missing():
    """На пустой БД создаётся admin/admin с is_superuser=True."""
    assert not User.objects.filter(username="admin").exists()

    call_command("ensure_admin")

    user = User.objects.get(username="admin")
    assert user.is_superuser
    assert user.is_staff
    assert user.is_active
    assert user.check_password("admin")


@pytest.mark.django_db
def test_idempotent_second_run():
    """Повторный запуск не меняет пароль и не падает."""
    call_command("ensure_admin")
    user_before = User.objects.get(username="admin")
    pw_hash_before = user_before.password

    # Второй запуск — без --reset пароль не должен меняться
    call_command("ensure_admin")
    user_after = User.objects.get(username="admin")
    assert user_after.password == pw_hash_before


@pytest.mark.django_db
def test_reset_flag_changes_password():
    """С флагом --reset пароль обновляется."""
    call_command("ensure_admin", "--password", "old_pw")
    user = User.objects.get(username="admin")
    assert user.check_password("old_pw")

    call_command("ensure_admin", "--reset", "--password", "new_pw")
    user.refresh_from_db()
    assert user.check_password("new_pw")


@pytest.mark.django_db
def test_custom_username_and_password():
    """Кастомные логин/пароль через аргументы."""
    call_command("ensure_admin", "--username", "boss", "--password", "secret42")

    user = User.objects.get(username="boss")
    assert user.is_superuser
    assert user.check_password("secret42")


@pytest.mark.django_db
def test_employee_created_with_admin_role():
    """У созданного пользователя появляется Employee с ролью admin."""
    call_command("ensure_admin")

    user = User.objects.get(username="admin")
    emp = Employee.objects.get(user=user)
    assert emp.role == Employee.ROLE_ADMIN


@pytest.mark.django_db
def test_restores_flags_if_revoked():
    """Если у существующего пользователя сняли is_superuser — команда вернёт."""
    call_command("ensure_admin")
    user = User.objects.get(username="admin")
    user.is_superuser = False
    user.is_staff = False
    user.save()

    call_command("ensure_admin")

    user.refresh_from_db()
    assert user.is_superuser
    assert user.is_staff


@pytest.mark.django_db
def test_password_from_env(monkeypatch):
    """Пароль берётся из переменной окружения ADMIN_PASSWORD."""
    monkeypatch.setenv("ADMIN_PASSWORD", "env_password")

    call_command("ensure_admin")

    user = User.objects.get(username="admin")
    assert user.check_password("env_password")
