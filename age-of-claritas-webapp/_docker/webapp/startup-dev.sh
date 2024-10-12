#!/bin/sh
# python manage.py collectstatic --noinput
python manage.py migrate --noinput
# python manage.py loaddata registratation/fixtures/ethnicity.json
# python manage.py loaddata registratation/fixtures/majors.json
python manage.py runserver 0.0.0.0:8000