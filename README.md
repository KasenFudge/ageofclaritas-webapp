# Environment Files
For environment files, which are not included in the GitHub Repo, you'll need to make a .env folder.
I then recommend putting the following in it.
## /.env/.env.app-ageofclaritas
This is an example of the environment file for the age of claritas application
```
SECRET_KEY=//
DEBUG=True
DB_ENGINE=django.db.backends.postgresql
DB_NAME=aocdb
DB_USER=aocdb_admin
DB_PASSWORD=//
DB_HOST=127.0.0.1
DB_PORT=5432
ALLOWED_HOSTS='["127.0.0.1", "localhost", "45.55.63.12", "ageofclaritas.tech"]'
MEDIA_ROOT=G:/data/aoc-django/

MLH_CLIENT_ID=//
MLH_SECRET_KEY=//

OAUTH_SITE_ID=5
OAUTH_HTTPS='http'
LOG_ROOT=H:/data/aoc-django/
STATIC_ROOT=H:/data/static-django/

EMAIL_API_KEY=//
EMAIL_SENDER_DOMAIN=mg.ageofclaritas.tech
EMAIL_FROM_EMAIL=noreply@ageofclaritas.tech
EMAIL_FROM_NAME=Age of Claritas
EMAIL_SERVER_EMAIL=team@ageofclaritas.tech
```
## /.env/.env.docker/
This is an example of the environment file for the docker containers
```
#database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=aocdb
DB_USER=aocdb_admin
DB_PASSWORD=xxxxxxxxxxx
DB_SUPER_PASSWORD=xxxxxxxxxxx
DB_HOST=db
DB_PORT=5432
DB_PORT_EXT=5435

#django/docker paths
AOC_WEB_APP_ROOT=/home/ageofclaritas/apps/ageofclaritas-webapp # What is this path supposed to point to
MEDIA_ROOT=/home/ageofclaritas/webdata/media
STATIC_ROOT=/home/ageofclaritas/webdata/static
LOG_ROOT=/home/ageofclaritas/logs/

#django
SECRET_KEY=xxxxxxxxxxx
DEBUG=True
ALLOWED_HOSTS='["127.0.0.1", "localhost", "45.55.63.12", "ageofclaritas.tech"]'

#email
EMAIL_API_KEY=xxxxxxxxxxx
EMAIL_SENDER_DOMAIN=mg.ageofclaritas.tech
EMAIL_FROM_EMAIL=noreply@ageofclaritas.tech
EMAIL_SERVER_EMAIL=team@ageofclaritas.tech

#docker
PYTHON_VERSION=3.12.6
```

## Using a Virtual Environment
I also recommend creating a a virtual environment and running it during development.
To create a Virtual Environment, type and run the following in a terminal:
```
$ python -m venv .env/venv
```
This will create a virtual environment called venv in the .env folder.
Then to run it, you type the path to the Activate Script into a terminal (on Windows).
In the above case (from the main directory):
```
$ .env/venv/scripts/activate
```
This may work differently for MacOS/Linux systems.
Then to deactivate, you just type deactivate into a terminal.
```
$ deactivate
```