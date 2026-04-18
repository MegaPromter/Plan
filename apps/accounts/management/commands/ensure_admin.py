"""
Management command: создаёт суперпользователя admin/admin, если его нет.

Используется при первом развёртывании программы — чтобы сразу был рабочий
аккаунт администратора без необходимости запускать `createsuperuser`.

Запуск:
    python manage.py ensure_admin                 # admin / admin
    python manage.py ensure_admin --password xxx  # свой пароль
    python manage.py ensure_admin --reset         # сбросить пароль, если уже есть

Команда идемпотентна — безопасно запускать многократно.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Создаёт суперпользователя admin, если его нет (идемпотентно)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="admin",
            help="Логин администратора (по умолчанию: admin)",
        )
        parser.add_argument(
            "--password",
            default=None,
            help=(
                "Пароль. Если не указан — берётся из переменной окружения "
                "ADMIN_PASSWORD, а если и её нет — используется 'admin'."
            ),
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Сбросить пароль, даже если пользователь уже существует.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        username = opts["username"]
        # Пароль: явный аргумент → переменная окружения → дефолт 'admin'
        password = opts["password"] or os.environ.get("ADMIN_PASSWORD") or "admin"
        reset = opts["reset"]

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "is_superuser": True,
                "is_staff": True,
                "is_active": True,
            },
        )

        if created:
            # Новый пользователь — всегда задаём пароль
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"[ensure_admin] Создан суперпользователь '{username}' "
                    f"с паролем '{password}'."
                )
            )
        else:
            # Пользователь уже есть
            changed = False
            # Подстрахуемся: если кто-то снял флаги — вернём
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if reset:
                user.set_password(password)
                changed = True
            if changed:
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[ensure_admin] Пользователь '{username}' обновлён "
                        f"(reset={reset})."
                    )
                )
            else:
                self.stdout.write(
                    f"[ensure_admin] Пользователь '{username}' уже существует "
                    f"— изменения не нужны."
                )

        # Связанный Employee с ролью admin — нужен для прав в бизнес-логике
        # (проверяется через _cfg.isAdmin, get_visibility_filter и т.д.)
        try:
            from apps.employees.models import Employee

            emp, emp_created = Employee.objects.get_or_create(
                user=user,
                defaults={
                    "last_name": "Администратор",
                    "first_name": "Системный",
                    "role": Employee.ROLE_ADMIN,
                },
            )
            if not emp_created and emp.role != Employee.ROLE_ADMIN:
                emp.role = Employee.ROLE_ADMIN
                emp.save(update_fields=["role"])
                self.stdout.write(
                    f"[ensure_admin] Employee для '{username}' обновлён: "
                    f"role=admin."
                )
            elif emp_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[ensure_admin] Создан Employee для '{username}' "
                        f"с ролью 'admin'."
                    )
                )
        except Exception as e:
            # Если модель Employee ещё не мигрирована или структура другая —
            # не валим команду, админ-юзер уже создан.
            self.stdout.write(
                self.style.WARNING(f"[ensure_admin] Не удалось создать Employee: {e}")
            )
