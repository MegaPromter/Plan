# Запуск planapp_django

## Требования
- Python 3.11
- PostgreSQL 15
- pip

## 1. Установить зависимости

```bash
cd D:\Program\Body\planapp_django
pip install -r requirements.txt
```

## 2. Создать базу данных PostgreSQL

```sql
CREATE DATABASE planapp_django;
```

## 3. Настроить переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

```bash
copy .env.example .env
```

Отредактируйте `.env`:
```
SECRET_KEY=<сгенерируйте длинный случайный ключ>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://postgres:<пароль>@localhost:5432/planapp_django
```

Сгенерировать SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 4. Применить миграции

```bash
python manage.py makemigrations employees works accounts
python manage.py migrate
```

## 5. Создать суперпользователя

```bash
python manage.py createsuperuser
```

## 6. Создать профиль Employee для суперпользователя

После создания суперпользователя зайдите в Django Admin (`/admin/`) и создайте запись `Employee` для него вручную (или через shell):

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from apps.employees.models import Employee, NTCCenter, Department

# Создать структуру (если нужно)
center = NTCCenter.objects.create(code="НТЦ-1", name="НТЦ")
dept   = Department.objects.create(code="001", name="Отдел 1")

# Привязать к суперпользователю
user = User.objects.get(username="admin")
Employee.objects.create(
    user=user,
    last_name="Администратор",
    first_name="Главный",
    patronymic="",
    role="admin",
    ntc_center=center,
    department=dept,
)
```

## 7. Запустить сервер разработки

```bash
python manage.py runserver 0.0.0.0:8000
```

Открыть в браузере: http://localhost:8000/

## Структура приложений

| Приложение | URL-префикс | Описание |
|---|---|---|
| accounts | /accounts/ | Авторизация, профиль, смена пароля |
| employees | /employees/ | Сотрудники, отпуска, KPI |
| works | /works/ | Работы (ПО/ПП), извещения, отчёты |
| admin | /admin/ | Django Admin |

## Роли пользователей

| Роль | Что видит в работах |
|---|---|
| `admin` | Все работы |
| `ntc_head` | Работы своего НТЦ-центра |
| `ntc_deputy` | Работы своего НТЦ-центра |
| `dept_head` | Работы своего отдела |
| `dept_deputy` | Работы своего отдела |
| `sector_head` | Работы своего сектора |
| `user` | Только свои работы (исполнитель) |

Роли `admin`, `ntc_head`, `ntc_deputy`, `dept_head`, `dept_deputy`, `sector_head` имеют право на создание/редактирование/удаление.
Роль `user` — только чтение.
