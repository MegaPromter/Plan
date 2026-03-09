#!/bin/bash
# Стартовый скрипт для Railway — миграции, загрузка данных, запуск сервера
set -e

echo "=== Running migrations ==="
python manage.py migrate --noinput

# Загрузка данных из дампа, если файл существует
if [ -f data_dump.json ]; then
    FORCE="${FORCE_LOADDATA:-0}"

    # Проверяем, есть ли уже данные в БД
    USERS=$(python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth import get_user_model
print(get_user_model().objects.count())
" 2>/dev/null || echo "0")

    if [ "$USERS" = "0" ] || [ "$USERS" = "" ] || [ "$FORCE" = "1" ]; then
        echo "=== Flushing DB before loading dump ==="
        python manage.py flush --noinput
        echo "=== Loading data dump ==="
        python manage.py loaddata data_dump.json
        echo "=== Data loaded successfully ==="
    else
        echo "=== Skipping loaddata (DB has $USERS users, set FORCE_LOADDATA=1 to override) ==="
    fi
fi

echo "=== Starting gunicorn ==="
exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
