from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Авторизация"

    def ready(self):
        import apps.accounts.signals  # noqa: F401 — подключаем сигналы auth
