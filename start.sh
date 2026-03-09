#!/bin/bash
# Стартовый скрипт для Railway — миграции + запуск сервера
set -e

echo "=== Running migrations ==="
python manage.py migrate --noinput

echo "=== Starting gunicorn ==="
exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
