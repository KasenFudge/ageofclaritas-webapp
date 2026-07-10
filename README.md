# Age of Claritas Webapp

A Django-based web application for the *Age of Claritas* project.

## Workflow Overview

* **Development:** Local environment using Python virtual environments, Tailwind CSS watch mode, and full migration capabilities.
* **Production:** Containerized deployment using Docker Compose. Note: The production Droplet is configured to run the application only; **all database migrations must be performed in development and pushed via code/database updates.**

---

## Development Setup

### 1. Local Environment

For local development, manage dependencies and migrations outside of Docker to keep your environment lean:

1. **Virtual Environment:**

    ```bash
    python -m venv .venv
    # Activate:
    # Windows: .venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    ```

2. **Tailwind CSS:**
    Run this command while developing to keep your `output.css` updated automatically:

    ```bash
    npx @tailwindcss/cli -i ./static/src/main.css -o ./static/dist/output.css --watch
    ```

### 2. Database Migrations

Migrations are managed in the development environment. After creating new models or fields:

1. Run `python manage.py makemigrations <app_name>`
2. Run `python manage.py migrate`
3. Commit these changes to Git so they are available for deployment.

---

## Production Deployment (DigitalOcean)

The production server pulls the latest code and restarts services.

### Initial Setup

Follow these steps only when first initializing the Droplet:

1. **Start Services:**

    ```bash
    docker compose up -d --build
    ```

2. **Create Admin:**

    ```bash
    docker compose run --rm webapp python manage.py createsuperuser
    ```

### Routine Updates

When deploying code changes to the production Droplet:

1. `git pull`
2. `docker compose up -d --build` (This restarts your containers with the new code).
3. *Note: Migrations are handled by your build/deployment pipeline or manual trigger during the update process.*

---

## Maintenance & Troubleshooting

### Database Backups

To create a standard SQL backup:

   ```bash
   docker exec ageofclaritas_db pg_dump -U <USER> -d <DB_NAME> > db_backup_$(date +%F).sql
   ```

For a data-only backup (safer for schema migrations):

   ```bash
   docker exec ageofclaritas_db pg_dump --column-inserts --data-only -U <USER> -d <DB_NAME> > inserts_backup_$(date +%F).sql
   ```

### Migrations

To run migrations and apply database changes (ensure you are in the directory for the site you wish to update):

   ```bash
   docker exec -it ageofclaritas_webapp python manage.py migrate
   ```

### Static Files

If CSS/Images break after an update:

   ```bash
   docker exec -it ageofclaritas_webapp python manage.py collectstatic --noinput
   ```

### Logs

To debug a service (e.g., webapp or db):

   ```bash
   docker compose logs -f <service_name>
   ```

## Configuration

Ensure a `.env` file exists in your root directory. Never commit this file to version control.

   ```.env
   # SECURITY
   SECRET_KEY='your-secret-key'
   DEBUG=False

   # ROOTS
   STATIC_ROOT=/var/www/static/aoc
   MEDIA_ROOT=/var/www/media/aoc

   # DATABASE
   POSTGRES_DB=aoc_db
   POSTGRES_USER=aocdb_admin
   POSTGRES_PASSWORD=your_secure_password
   POSTGRES_HOST=db
   POSTGRES_PORT=5432

   # HOSTS
   ALLOWED_HOSTS='["ageofclaritas.com", "beta.ageofclaritas.com", "127.0.0.1"]'
   ```
