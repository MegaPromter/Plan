#!/bin/bash
# Release command for Railway — runs on each deploy before start
set -e

echo "=== Running migrations ==="
python manage.py migrate --noinput

# Load data dump if it exists
if [ -f data_dump.json ]; then
    echo "=== Flushing DB before loading dump ==="
    python manage.py flush --noinput
    echo "=== Loading data dump ==="
    python manage.py loaddata data_dump.json
    echo "=== Data loaded successfully ==="
fi

echo "=== Release complete ==="
