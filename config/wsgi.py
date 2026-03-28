import os  # стандартная библиотека для работы с переменными окружения

from django.core.wsgi import get_wsgi_application  # фабрика WSGI-приложения Django

# Устанавливаем переменную среды DJANGO_SETTINGS_MODULE, если она не задана извне.
# Значение 'config.settings' указывает Python-путь к модулю настроек проекта.
# Это позволяет запускать проект командой: gunicorn config.wsgi:application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Создаём WSGI-callable объект приложения.
# WSGI-сервер (gunicorn, uWSGI и т.д.) вызывает этот объект для обработки каждого HTTP-запроса.
# Django инициализирует все приложения, middleware и маршруты при первом вызове.
application = get_wsgi_application()
