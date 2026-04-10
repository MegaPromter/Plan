# planapp_django

## Запуск проекта
- `python manage.py runserver 0.0.0.0:8000`
- Зависимости: `pip install -r requirements.txt` (прод), `pip install -r requirements-dev.txt` (дев)
- `.env` файл для конфигурации (DATABASE_URL, SECRET_KEY, DEBUG)

## Запуск тестов
- `python -m pytest tests/ -x -q`
- Перед каждым коммитом — тесты обязательны, все должны быть зелёными

## Стек
- Django 3.2 / Python 3.11 / PostgreSQL 15
- Frontend: Vanilla JS (plan.js, production_plan.js, enterprise.js) + Vue 3/Vite (миграция в процессе)
- CSS: variables.css → components.css → модульные файлы
- Деплой: Docker + gunicorn + whitenoise

## Структура проекта
- `apps/accounts` — авторизация, профили
- `apps/employees` — сотрудники, отделы, секторы, роли
- `apps/works` — модели Work, PPProject, Project, Notice, WorkCalendar, Holiday
- `apps/api` — REST API, middleware, утилиты, аудит
- `apps/enterprise` — портфель проектов, ГГ, сквозной график, сценарии
- `config/settings.py` — настройки Django
- `templates/` — Django-шаблоны по приложениям
- `static/js/` — SPA-модули, `static/css/` — стили, `static/vue/` — Vue 3 билды

## Ключевые URL
- `/works/plan/` — план задач (СП)
- `/works/production-plan/` — производственный план (ПП)
- `/works/projects/` — управление проектами (УП)
- `/works/notices/` — журнал извещений (ЖИ)
- `/works/enterprise/` — управление предприятием
- `/works/work-calendar/` — производственный календарь
- `/api/health/` — health check

## Конвенции кода
- Язык общения и комментариев в коде — **русский**
- Общие стили только в `components.css`, модульные — в `{module}.css`, inline `<style>` запрещён
- Справочные данные — через management command `seed_data` с `get_or_create`, НЕ fixtures
- `generate_row_code(project)` — атомарная генерация row_code, read-only в ПП

## Роли и доступ
- Роли: admin, ntc_head, ntc_deputy, dept_head, dept_deputy, sector_head, chief_designer, deputy_gd_econ, user
- `is_writer` — все кроме user; user = только чтение
- Видимость: `get_visibility_filter()` в `apps/api/utils.py`, зависит от `show_all_depts`

## Правила работы
- `git push` — ТОЛЬКО по явной команде пользователя («деплой», «пуш»)
- `git commit` — сначала тесты, потом коммит
- Верификация — молча через preview tools, не описывать результаты
- Не использовать `preview_screenshot` (зависания), только `preview_snapshot`/`preview_inspect`/`preview_console_logs`
- Браузер: только Brave (не использовать Chrome MCP tools)
- Пользователь учится программированию — кратко пояснять концепции по ходу работы (2-3 предложения)

## Линтеры (dev)
- black, flake8, isort

## Деплой
- **Деплоить сюда: https://managesystems.ru/**
- Деплой ТОЛЬКО по явной команде пользователя («деплой», «пуш»)
- `git push` ≠ деплой на прод. Пуш на GitHub — это только пуш кода в репозиторий
- Redis для сессий при `CACHE_BACKEND=redis`

## Сервер (prod) — Yandex Cloud
- **IP:** 89.169.163.1, SSH: `ssh -i ~/.ssh/id_ed25519_vps fynjy@89.169.163.1`
- **OS:** Ubuntu 24.04 LTS
- **Путь:** `/opt/planapp/`, venv: `/opt/planapp/venv/`
- **nginx** → `127.0.0.1:8000` → gunicorn (2 воркера)
- **SSL:** Let's Encrypt (certbot, автопродление)
- **PostgreSQL:** локальная, `planapp_db` (user: planapp, pass: planapp_secure_2026)
- **Процедура деплоя:** `git push` → SSH → `cd /opt/planapp && git pull && source venv/bin/activate && pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput && sudo systemctl restart gunicorn`

## Frontend-стек
- Новые страницы: Django templates + HTMX + Alpine.js
- Существующие SPA: vanilla JS (не мигрировать на Vue)
- При доработке простых SPA (notice_list, projects_spa, work_calendar_spa): переводить на HTMX + Alpine.js

## Обязательные правила
- Делай коммит после каждого серьёзного изменения
- Деплой только по команде пользователя
- Не использовать `preview_screenshot` — вызывает зависания. Для верификации: `preview_snapshot`, `preview_inspect`, `preview_console_logs`
- Верификация — молча проверять, не описывать результаты
- Общение только на русском
- Тесты перед каждым коммитом: `python -m pytest tests/ -x -q`
- Общие стили только в `components.css`, без дублирования между модулями
- Справочники деплоятся через management command (get_or_create), НЕ fixtures
- Пользователь учится программированию — кратко пояснять концепции по ходу работы
- Браузер: только Brave (не использовать Chrome MCP tools)
