# Базовый класс конфигурации Django-приложения
from django.apps import AppConfig


# Конфигурация приложения works
class WorksConfig(AppConfig):
    # Тип первичного ключа по умолчанию для всех моделей приложения
    default_auto_field = "django.db.models.BigAutoField"
    # Полное имя модуля приложения (для INSTALLED_APPS)
    name = "apps.works"
    # Короткий метка-идентификатор приложения (используется в миграциях)
    label = "works"
    # Человекочитаемое название приложения (отображается в Django Admin)
    verbose_name = "Работы"
