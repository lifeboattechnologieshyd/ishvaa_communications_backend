#!/bin/sh
set -e

echo "Starting Ishvaa Communications backend..."

cd /project

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --threads 4 \
  --timeout 120 \
  --access-logfile '-' \
  --error-logfile '-'