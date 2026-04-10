# Базовый класс конфигурации Django-приложения
from django.apps import AppConfig


# Конфигурация приложения employees
class EmployeesConfig(AppConfig):
    # Тип первичного ключа по умолчанию для всех моделей приложения
    default_auto_field = "django.db.models.BigAutoField"
    # Полное имя модуля приложения (для INSTALLED_APPS)
    name = "apps.employees"
    # Короткий метка-идентификатор приложения (используется в миграциях)
    label = "employees"
    # Человекочитаемое название приложения (отображается в Django Admin)
    verbose_name = "Сотрудники"

    def ready(self):
        # Импортируем модуль сигналов при запуске приложения —
        # это необходимо для регистрации обработчиков сигналов (например, post_save).
        # noqa: F401 — подавляем предупреждение линтера об «неиспользуемом» импорте
        import apps.employees.signals  # noqa: F401 — регистрация сигналов
