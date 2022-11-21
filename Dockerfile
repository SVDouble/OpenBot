###########
# BUILDER #
###########

FROM python:3.11-slim as builder
WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY ./requirements.txt .

# Install dependencies
RUN set -ex \
    && BUILD_DEPS=" \
    build-essential \
    libpcre3-dev \
    libpq-dev \
    git \
    " \
    && apt-get update && apt-get install -y --no-install-recommends $BUILD_DEPS \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt


#########
# FINAL #
#########

FROM python:3.11-slim

LABEL maintainer="Valentin Safronov <svdouble@hotmail.com>"

# Create a group and user to run our app
RUN groupadd -r app && useradd --no-log-init -r -g app app

# Create directory for the app user and the app itself
ENV HOME=/home/app
ENV APP_HOME=$HOME
WORKDIR $APP_HOME

# Install packages needed to run your application (not build deps):
#   mime-support -- for mime types when serving static files
#   postgresql-client -- for running database commands
# We need to recreate the /usr/share/man/man{1..8} directories first because
# they were clobbered by a parent image.
RUN set -ex \
    && RUN_DEPS=" \
    libpcre3 \
    mime-support \
    postgresql-client \
    netcat \
    " \
    && seq 1 8 | xargs -I{} mkdir -p /usr/share/man/man{} \
    && apt-get update && apt-get install -y --no-install-recommends $RUN_DEPS \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels/ \
    && mkdir -p "$APP_HOME" \
    && chown -Rf app:app "$APP_HOME"

# copy source files
COPY --chown=app:app ./ "$APP_HOME"

# port for the webhooks
# bot is running behind nginx
# so we don't have to terminate SSL ourselves
EXPOSE 80

ENV PYTHONPATH=$APP_HOME

# Change to a non-root user
USER app:app

ENTRYPOINT ["python", "-m", "app"]
