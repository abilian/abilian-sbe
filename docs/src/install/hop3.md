# On Hop3

[Hop3](https://hop3.cloud/) runs an application's processes and provides its database and its Redis. A site deployed on Hop3 is a small project of its own, with no code: one file pins the version of Abilian SBE, from PyPI, and another says how to run it. The package holds everything the application needs: its scripts, its compiled translations and its migrations.

## The project

`pyproject.toml`:

```toml
[project]
name = "my-extranet"
version = "1.0"
requires-python = ">=3.12"
dependencies = ["abilian-sbe[postgres]==2.0.0"]
```

Run `uv lock` to write `uv.lock`, which pins every dependency.

`hop3.toml` names your application and its domain:

```toml
[metadata]
id = "my-extranet"

[domains]
list = ["extranet.example.org"]

[run]
# Before each start: the tables made on the first one, then kept up to date.
before-run = ["flask preparedb"]
start = "gunicorn abilian.wsgi:app -b 0.0.0.0:$PORT --workers 4 --log-file -"
start-timeout = 180
# For previews and search inside documents.
packages = ["poppler-utils", "imagemagick", "libreoffice-nogui"]

[run.workers]
worker = "flask worker"
scheduler = "flask scheduler"

[healthcheck]
path = "/health"
contains = "OK"

[[addons]]
type = "postgres"

[[addons]]
type = "redis"

# The files, the search index and the caches, which a new deployment keeps.
[[volumes]]
name = "instance"
target = "instance"

[proxy]
max-body-size = "200m"

[env]
FLASK_APP = "abilian.wsgi"
FLASK_INSTANCE_PATH = "instance"
FLASK_SECRET_KEY = { generate = "hex", length = 64 }
FLASK_PRODUCTION = "true"
FLASK_PREFERRED_URL_SCHEME = "https"
FLASK_SITE_NAME = "My extranet"
FLASK_BABEL_ACCEPT_LANGUAGES = '["fr", "en"]'
FLASK_PRIVATE_SITE = "true"

[env.computed]
FLASK_SQLALCHEMY_DATABASE_URI = "${DATABASE_URL}"
FLASK_REDIS_URI = "${REDIS_URL}"
FLASK_DRAMATIQ_BROKER_URL = "${REDIS_URL}"
FLASK_DRAMATIQ_ABORT_REDIS_URL = "${REDIS_URL}"
FLASK_DRAMATIQ_RATE_LIMIT_REDIS_URL = "${REDIS_URL}"
FLASK_SERVER_NAME = "${HOST_NAME}"
```

Once the PostgreSQL and Redis addons are declared, Hop3 hands their addresses to the application, as `DATABASE_URL` and `REDIS_URL`. [Configuration](configuration.md) lists the other settings.

## Before the first deployment

Set the settings that are secrets, which `hop3.toml` leaves out on purpose:

```bash
hop3 env set --app my-extranet FLASK_MAIL_SERVER=smtp.example.org
hop3 env set --app my-extranet FLASK_MAIL_USERNAME=… FLASK_MAIL_PASSWORD=…
hop3 env set --app my-extranet FLASK_MAIL_SENDER=extranet@example.org
```

## Deploying

From the project:

```bash
hop3 deploy
```

The first start creates the tables. Then create the first administrator, in the application's environment:

```bash
hop3 run --app my-extranet flask createuser --role admin --name "Ada Lovelace" ada@example.org a-password
```

## Upgrading

Change the version of `abilian-sbe` in `pyproject.toml`, run `uv lock`, and deploy: the migrations run before the application starts.

## Moving an existing site

Empty the database Hop3 created, import a dump of the old one into it (`hop3 addon postgres import`), copy the old `data/files` folder into the volume's `data/files`, and deploy again: `flask preparedb` finds the old tables and brings them up to date. Then run `flask reindex` once, to rebuild the search index.
