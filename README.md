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
POSTGRES_PASSWORD=J7:G5?FsCe7h5m4
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