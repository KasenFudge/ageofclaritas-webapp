# Setup on Hosting Service

The application is containerized using Docker. These instructions assume you have Docker and Docker Compose installed on your host (e.g., DigitalOcean Droplet).

## Initial Deployment & Database Setup

If you are setting up the project for the first time or performing a fresh database reset, follow these steps in order:

1. **Build and Start Containers** `docker compose up -d --build`  
   *This builds the images and starts the services in the background.*

2. **Generate Migrations (App Specific)** `docker compose run --rm webapp python manage.py makemigrations accounts`  
   *Crucial: We generate 'accounts' first to ensure the CustomUser model is properly initialized before other apps dependency-link to it.*

3. **Generate Remaining Migrations** `docker compose run --rm webapp python manage.py makemigrations`  
   *This captures changes in the Events, Rulebook, and other applications.*

4. **Apply Database Schema** `docker compose run --rm webapp python manage.py migrate`  
   *This creates the actual tables in the Postgres container.*

5. **Create Admin Account** `docker compose run --rm webapp python manage.py createsuperuser`  
   *Note: You will be prompted for a username, email, and Date of Birth (as required by our CustomUser model).*

## Maintenance Commands

### Accessing Database
In the case the database needs to be accessed, run:
`docker exec -it aoc_db psql -U aocdb_admin -d aoc_db`
NOTE: if your database configuration is different than the example provided below in Environment Files, this will need modified.

### Static Files
If CSS or images are not appearing correctly after an update, run:
`docker exec -it aoc_webapp python manage.py collectstatic --noinput`

### Viewing Logs
To troubleshoot a service (e.g., Nginx or Webapp):
`docker compose logs -f [service_name]`

# Environment Files
For environment files, which are not included in the GitHub Repo, you'll need to make a .env folder.
I then recommend putting the following in it.\n
Note that anything that looks empty, like "//" or "xxxxxxxxxxx" needs to be filled in on your end.
## ./.env
This is an example of the environment file for the age of claritas application
```
# SECURITY (Used by Django)
SECRET_KEY='xxxxxxxxxxx'
DEBUG=False

# ROOTS (Used in constructing paths to store data)
STATIC_ROOT=/var/www/static/aoc
MEDIA_ROOT=/var/www/media/aoc

# DATABASE (Used by BOTH Postgres and Django)
POSTGRES_DB=aoc_db
POSTGRES_USER=aocdb_admin
POSTGRES_PASSWORD=
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Who can Host
ALLOWED_HOSTS='["kasenfudge.me", "www.kasenfudge.me", "167.99.232.224", "127.0.0.1", "localhost"]'
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