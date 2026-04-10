"""
Тесты ColSettings API.
"""

import json

import pytest
from django.test import Client

from apps.employees.models import Employee


@pytest.mark.django_db
class TestColSettings:
    def test_requires_auth(self):
        resp = Client().post(
            "/api/col_settings/",
            json.dumps({"plan_col1": 100}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_save_col_settings(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.post(
            "/api/col_settings/",
            json.dumps({"plan_col1": 150, "plan_col2": 200}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        emp = Employee.objects.get(user=admin_user)
        assert emp.col_settings.get("plan_col1") == 150
        assert emp.col_settings.get("plan_col2") == 200

    def test_merge_not_replace(self, admin_user):
        """Новые настройки мёрджатся с существующими, а не заменяют."""
        emp = Employee.objects.get(user=admin_user)
        emp.col_settings = {"existing_key": 42}
        emp.save(update_fields=["col_settings"])

        c = Client()
        c.force_login(admin_user)
        c.post(
            "/api/col_settings/",
            json.dumps({"new_key": 99}),
            content_type="application/json",
        )

        emp.refresh_from_db()
        assert emp.col_settings.get("existing_key") == 42
        assert emp.col_settings.get("new_key") == 99

    def test_reset_widths(self, admin_user):
        """_reset_widths удаляет ширины но сохраняет show_all_depts."""
        emp = Employee.objects.get(user=admin_user)
        emp.col_settings = {"plan_col1": 100, "show_all_depts": True}
        emp.save(update_fields=["col_settings"])

        c = Client()
        c.force_login(admin_user)
        c.post(
            "/api/col_settings/",
            json.dumps({"_reset_widths": True}),
            content_type="application/json",
        )

        emp.refresh_from_db()
        assert emp.col_settings.get("show_all_depts") is True
        assert "plan_col1" not in emp.col_settings

    def test_bad_json_400(self, admin_user):
        c = Client()
        c.force_login(admin_user)
        resp = c.post("/api/col_settings/", "not-json", content_type="application/json")
        assert resp.status_code == 400
