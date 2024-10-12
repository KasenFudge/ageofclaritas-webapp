#!/bin/sh
python manage.py collectstatic --noinput
python manage.py migrate --noinput
gunicorn --access-logfile - --error-logfile - --workers 3 --reload --bind 0.0.0.0:8000 AoCSite.wsgi:application