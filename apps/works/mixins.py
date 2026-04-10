"""
Общие миксины для SPA-view приложения works.
"""

import json


class SPAContextMixin:
    """Общий контекст для всех SPA-страниц: role, username, is_writer и т.д."""

    include_col_settings = False

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = getattr(self.request.user, "employee", None)
        ctx["role"] = (
            emp.role if emp else ("admin" if self.request.user.is_superuser else "user")
        )
        ctx["username"] = emp.short_name if emp else self.request.user.username
        ctx["user_position"] = (
            emp.get_position_display() if emp and emp.position else ""
        )
        ctx["user_dept"] = emp.department.code if emp and emp.department else ""
        ctx["is_writer"] = emp.is_writer if emp else self.request.user.is_superuser
        if self.include_col_settings:
            col_settings = {}
            if emp and emp.col_settings:
                col_settings = (
                    emp.col_settings if isinstance(emp.col_settings, dict) else {}
                )
            # Экранируем '</' для предотвращения выхода из <script> тега
            ctx["col_settings"] = json.dumps(col_settings).replace("</", "<\\/")
        return ctx
