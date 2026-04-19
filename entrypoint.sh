#!/bin/sh
set -e

echo "=== Applying migrations ==="
python manage.py migrate --noinput

echo "=== Seeding reference data ==="
python manage.py seed_calendar
python manage.py seed_soft_stages
python manage.py seed_centers

echo "=== Starting server ==="
exec "$@"
