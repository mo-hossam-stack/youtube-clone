#!/bin/bash
set -e

echo "==> Running migrations..."
python manage.py migrate --noinput 2>&1

echo "==> Startup complete."
exec "$@"
