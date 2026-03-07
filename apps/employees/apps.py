from django.apps import AppConfig

class EmployeesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name  = 'apps.employees'
    label = 'employees'
    verbose_name = 'Сотрудники'

    def ready(self):
        import apps.employees.signals  # noqa: F401 — регистрация сигналов
