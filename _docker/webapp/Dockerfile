
# https://github.com/michaeloliverx/python-poetry-docker-example/blob/master/docker/Dockerfile
# Any arguments coming from the Docker Compose file must be listed here
# (they can also be given default values here)
ARG AOC_WEB_APP_ROOT
ARG PYTHON_VERSION

# ===================================================================
# First step - get all Python and build virtual environment
FROM python:${PYTHON_VERSION}-bullseye as python-base

# Arguments must be declared after a FROM to be used within that build step
ARG AOC_WEB_APP_ROOT

# This sets an environment variables in the container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

# ===================================================================
# Second step -builder-base is used to build dependencies (poetry, etc)
FROM python-base as builder-base
ARG AOC_WEB_APP_ROOT
ARG POETRY_VERSION

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        build-essential \
        libpq-dev

# Install Poetry - respects $POETRY_VERSION & $POETRY_HOME
ENV POETRY_VERSION=${POETRY_VERSION}
RUN curl -sSL https://install.python-poetry.org | python3 -

# We copy our Python requirements here to cache them
# and install only runtime deps using poetry
WORKDIR $PYSETUP_PATH
COPY ./poetry.lock ./pyproject.toml ./
RUN poetry install --no-dev  # respects

# ===================================================================
# Third step: 'development' stage installs all dev deps and can be used to develop code.
# For example using docker-compose to mount local volume under /app

FROM python-base as development
ARG AOC_WEB_APP_ROOT
WORKDIR ${AOC_WEB_APP_ROOT}

# Copying poetry and venv into image
COPY --from=builder-base $POETRY_HOME $POETRY_HOME
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH

# venv already has runtime deps installed we get a quicker install
WORKDIR $PYSETUP_PATH
RUN poetry install


# Copy application files into the container
# except things specified in the .dockerignore file
# maybe this only needs to happen in production?
WORKDIR ${AOC_WEB_APP_ROOT}
COPY . ./

#startup script isn't needed here, but it is in the production stage

# ===================================================================
# Fourth step: 'lint'
FROM development AS lint
RUN black --config ./pyproject.toml --check app tests
RUN isort --settings-path ./pyproject.toml --recursive --check-only
CMD ["tail", "-f", "/dev/null"]

# ===================================================================
# Fith step: 'test'
FROM development AS test
RUN coverage run --rcfile ./pyproject.toml -m pytest ./tests
RUN coverage report --fail-under 95

# ===================================================================
# Sixth step: 'production'stage uses the clean 'python-base' stage and copyies
# in only our runtime deps that were installed in the 'builder-base'
FROM python-base as production
# Arguments must be declared after a FROM to be used within that build step
ARG AOC_WEB_APP_ROOT
ARG STARTUP_SCRIPT
# WHY IS THIS NEEDED? can't we just use the ARG in the CMD?
ENV STARTUP_SCRIPT=${STARTUP_SCRIPT} 
WORKDIR ${AOC_WEB_APP_ROOT}

COPY --from=builder-base $VENV_PATH $VENV_PATH
# Add virtual environment to the system path
ENV PATH="$VENV_PATH:$PATH"

# Copy application files into the container
# except things specified in the .dockerignore file
# maybe this only needs to happen in production?
COPY . ./

# # Copy the setup script into the container
COPY ./_docker/webapp/${STARTUP_SCRIPT} ./

# Make sure setup script is executable
RUN chmod a+x "./$STARTUP_SCRIPT" 
# Make sure the setup script is in Unix format
RUN sed -i 's/\r$//' ./$STARTUP_SCRIPT

# Make the startup script the command used when starting the container
CMD ${AOC_WEB_APP_ROOT}${STARTUP_SCRIPT}