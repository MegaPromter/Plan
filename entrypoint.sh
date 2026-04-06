#!/bin/sh
set -e

echo "=== Applying migrations ==="
python manage.py migrate --noinput

echo "=== Seeding reference data ==="
python manage.py seed_calendar

echo "=== Starting server ==="
exec "$@"
