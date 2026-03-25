"""
Django settings for planapp_django.
Django 3.2 / Python 3.11 / PostgreSQL 15
"""
import os          # стандартная библиотека для работы с ОС (переменные среды, пути)
from pathlib import Path  # объектно-ориентированная работа с путями файловой системы

import environ  # библиотека django-environ для чтения .env-файлов

# BASE_DIR — корневая директория проекта (два уровня вверх от этого файла: config/ → корень)
BASE_DIR = Path(__file__).resolve().parent.parent

# --- Чтение .env -------------------------------------------------------
# Создаём объект environ с явным указанием типа и значения по умолчанию для DEBUG
env = environ.Env(
    DEBUG=(bool, False),  # если DEBUG не задан в .env — используем False (продакшн-безопасно)
)
# Читаем файл .env из корня проекта (если существует) и загружаем переменные в os.environ
_env_file = BASE_DIR / '.env'
if _env_file.is_file():
    environ.Env.read_env(_env_file)

# Секретный ключ Django — используется для подписи cookies, CSRF-токенов и т.д.
# В продакшне обязательно задавать через переменную среды SECRET_KEY
SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me')
DEBUG = env('DEBUG')

# В продакшне запрещаем инсекурный дефолтный ключ
if not DEBUG and SECRET_KEY == 'django-insecure-change-me':
    raise ValueError("SECRET_KEY не задан. Установите переменную среды SECRET_KEY.")
# Список разрешённых хостов, с которых принимаются запросы (защита от атак Host header)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# --- Приложения --------------------------------------------------------
# Список установленных Django-приложений (подключаются в порядке объявления)
INSTALLED_APPS = [
    'django.contrib.admin',        # стандартная админка Django
    'django.contrib.auth',         # система аутентификации и авторизации
    'django.contrib.contenttypes', # фреймворк типов контента (нужен для permissions)
    'django.contrib.sessions',     # поддержка серверных сессий
    'django.contrib.messages',     # фреймворк одноразовых сообщений (flash messages)
    'django.contrib.staticfiles',  # управление статическими файлами (css, js, img)

    # Наши приложения
    'apps.accounts',   # аутентификация, регистрация, профиль пользователя
    'apps.employees',  # модель Employee, роли, отделы, сектора, НТЦ
    'apps.works',      # основные модели: Work, TaskWork, PPWork, Project и т.д.
    'apps.api',        # REST API: все views, сериализаторы, middleware, утилиты
]

# --- Middleware ---------------------------------------------------------
# Цепочка обработчиков запросов/ответов (порядок важен — выполняются сверху вниз)
MIDDLEWARE = [
    'django.middleware.gzip.GZipMiddleware',              # сжатие ответов GZip (первым, чтобы сжать максимум)
    'django.middleware.security.SecurityMiddleware',       # заголовки безопасности (HSTS, X-Content-Type и др.)
    'whitenoise.middleware.WhiteNoiseMiddleware',          # раздача статических файлов без отдельного сервера
    'apps.api.middleware.RateLimitMiddleware',             # ограничение частоты запросов (rate limiting)
    'django.contrib.sessions.middleware.SessionMiddleware', # поддержка сессий (должен быть до auth)
    'django.middleware.common.CommonMiddleware',           # нормализация URL, добавление слеша
    'django.middleware.csrf.CsrfViewMiddleware',           # защита от CSRF-атак
    'django.contrib.auth.middleware.AuthenticationMiddleware', # привязывает пользователя к request.user
    'django.contrib.messages.middleware.MessageMiddleware',    # поддержка flash-сообщений
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # защита от Clickjacking (X-Frame-Options)
]

# Модуль с корневой конфигурацией URL-маршрутов проекта
ROOT_URLCONF = 'config.urls'

# --- Шаблоны -----------------------------------------------------------
# Конфигурация движков шаблонов Django
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',  # встроенный движок шаблонов Django
        'DIRS': [BASE_DIR / 'templates'],  # глобальная папка шаблонов на уровне проекта
        'APP_DIRS': True,  # автоматически искать шаблоны в папке templates/ каждого приложения
        'OPTIONS': {
            # Контекстные процессоры — добавляют переменные в контекст каждого шаблона
            'context_processors': [
                'django.template.context_processors.debug',    # добавляет переменную debug в шаблон
                'django.template.context_processors.request',  # добавляет объект request в шаблон
                'django.contrib.auth.context_processors.auth', # добавляет user и perms в шаблон
                'django.contrib.messages.context_processors.messages',  # добавляет messages в шаблон
                'apps.accounts.context_processors.active_nav',  # active_nav для подсветки сайдбара
            ],
        },
    },
]

# Путь к WSGI-приложению, которое запускает Django (используется gunicorn, uWSGI и т.д.)
WSGI_APPLICATION = 'config.wsgi.application'

# --- База данных (PostgreSQL 15) ---------------------------------------
# Конфигурация подключения к БД читается из переменной DATABASE_URL в .env
DATABASES = {
    'default': env.db(
        'DATABASE_URL',  # переменная среды с DSN вида postgres://user:pass@host:port/dbname
        default='postgres://postgres:postgres@localhost:5432/planapp_django',  # значение по умолчанию для локальной разработки
    )
}
# Переиспользование DB-соединений (10 мин) — без этого каждый запрос открывает новое
DATABASES['default']['CONN_MAX_AGE'] = 600
# Django 3.2: явно указываем тип первичного ключа по умолчанию
# BigAutoField — 64-битное целое (вместо 32-битного AutoField), предотвращает переполнение ID
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Аутентификация ----------------------------------------------------
AUTH_USER_MODEL = 'auth.User'   # стандартная модель Django

# URL для редиректа неаутентифицированных пользователей (страница входа)
LOGIN_URL          = '/accounts/login/'
# URL для редиректа после успешного входа (если не указан next в запросе)
LOGIN_REDIRECT_URL = '/accounts/dashboard/'
# URL для редиректа после выхода из системы
LOGOUT_REDIRECT_URL = '/accounts/login/'

# --- Интернационализация -----------------------------------------------
LANGUAGE_CODE = 'ru-ru'        # язык интерфейса — русский
TIME_ZONE     = 'Europe/Moscow' # часовой пояс — Москва (UTC+3)
USE_I18N      = True            # включить механизм перевода строк
USE_L10N      = True            # включить локализацию форматов чисел, дат и т.д.
USE_TZ        = True            # хранить даты в UTC, конвертировать при отображении

# --- Статика -----------------------------------------------------------
STATIC_URL  = '/static/'                                  # URL-префикс для статических файлов
STATICFILES_DIRS = [BASE_DIR / 'static']                  # папки со статикой в режиме разработки
STATIC_ROOT = BASE_DIR / 'staticfiles'                    # куда collectstatic собирает файлы для продакшна
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'  # WhiteNoise: сжатие + хеш в имени файла

# --- Медиа (загруженные файлы) ------------------------------------------
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- Кэш (используется rate-limiting middleware) -----------------------
_CACHE_BACKEND = env('CACHE_BACKEND', default='locmem')
if _CACHE_BACKEND == 'redis':
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/0'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'planapp-cache',
        }
    }

# --- Безопасность -------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True  # запрет MIME-sniffing: браузер не угадывает тип контента
SECURE_BROWSER_XSS_FILTER  = True  # включить фильтр XSS в старых браузерах (заголовок X-XSS-Protection)
SECURE_REFERRER_POLICY     = 'same-origin'  # передавать Referer только на тот же origin
X_FRAME_OPTIONS            = 'DENY'  # полностью запретить встраивание страниц в <iframe>

# Сессии
SESSION_COOKIE_HTTPONLY = True       # JS не может читать cookie сессии
SESSION_COOKIE_SAMESITE = 'Lax'     # Защита от CSRF через сторонние сайты
SESSION_COOKIE_AGE      = 8 * 3600  # Сессия живёт 8 часов (8 * 3600 секунд = 28800 с)

# CSRF
CSRF_COOKIE_HTTPONLY = False   # False — браузер должен читать для JS-запросов
CSRF_COOKIE_SAMESITE = 'Lax'  # SameSite=Lax: cookie отправляется при навигации с внешнего сайта

# Пароли — минимальная длина 8 символов
# Список валидаторов для проверки надёжности паролей при регистрации/смене пароля
AUTH_PASSWORD_VALIDATORS = [
    # Запрещает пароли, слишком похожие на данные пользователя (имя, email и т.д.)
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        # Требует минимальную длину пароля
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},  # минимальная длина — 8 символов
    },
    # Запрещает распространённые пароли из встроенного словаря Django (20 000 паролей)
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    # Запрещает полностью числовые пароли (например, "12345678")
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Блок продакшн-настроек безопасности (применяется только когда DEBUG=False)
if not DEBUG:
    SECURE_HSTS_SECONDS            = 31536000  # 1 год — время кэширования HSTS в браузере
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True       # распространить HSTS на все поддомены
    SECURE_HSTS_PRELOAD            = True       # разрешить включение в preload-список браузеров
    # Railway terminates SSL at the proxy level — не редиректим сами
    # Прокси-сервер (Railway) уже обрабатывает HTTPS, Django не должен делать redirect сам
    SECURE_SSL_REDIRECT            = False
    # Сообщаем Django, что запрос пришёл по HTTPS, если прокси выставил этот заголовок
    SECURE_PROXY_SSL_HEADER        = ('HTTP_X_FORWARDED_PROTO', 'https')
    # Передавать cookie сессии только по HTTPS (защита от перехвата)
    SESSION_COOKIE_SECURE          = True
    # Передавать CSRF cookie только по HTTPS (защита от перехвата)
    CSRF_COOKIE_SECURE             = True
    # Доверенные источники для CSRF (Django 4.0+ требует, но Django 3.2 тоже поддерживает)
    CSRF_TRUSTED_ORIGINS           = env.list('CSRF_TRUSTED_ORIGINS',
                                               default=['https://gukalo.ru'])

# --- Email -----------------------------------------------------------------
# Для отправки писем (сброс пароля и др.)
# Настраивается через .env: EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER,
# EMAIL_HOST_PASSWORD, EMAIL_USE_TLS, DEFAULT_FROM_EMAIL
EMAIL_BACKEND  = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST     = env('EMAIL_HOST', default='localhost')
EMAIL_PORT     = env.int('EMAIL_PORT', default=587)
EMAIL_HOST_USER     = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS  = env.bool('EMAIL_USE_TLS', default=True)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@planapp.local')

# --- Redis-сессии (если доступен Redis) ------------------------------------
if _CACHE_BACKEND == 'redis':
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'

# --- Логирование -----------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {'level': 'WARNING'},
        'apps': {'level': 'INFO'},
    },
}
