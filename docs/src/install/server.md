# On a server

This guide installs Abilian SBE on a Debian or Ubuntu server, here named `sbe.example.org`, behind nginx. The `example_config/` folder of the repository holds the example files it refers to.

## A dedicated user

```bash
sudo useradd -m -s /bin/bash sbe
sudo su - sbe
```

## System packages

```bash
sudo apt install build-essential git curl redis-server \
    poppler-utils imagemagick libreoffice-nogui \
    postgresql libpq-dev        # or: mariadb-server
```

Add `clamav-daemon` to scan uploaded files, and `nginx` and `certbot` for the web server. Node and npm are needed only to build the pages' scripts from a source checkout.

## uv and the application

Abilian SBE uses [uv](https://docs.astral.sh/uv/) to manage Python and its dependencies. It needs Python 3.12 or later, which uv downloads if the system lacks it.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone --depth 1 --branch main https://github.com/abilian/abilian-sbe-monorepo.git
cd abilian-sbe-monorepo
uv sync --no-dev --extra postgres
make front translations
```

`make front` builds the pages' scripts with Vite (it runs `npm install` in `vite/`); `make translations` compiles the translations. The commands below assume uv's environment: prefix them with `uv run`, or activate it with `. .venv/bin/activate`.

## The database

=== "PostgreSQL"

    ```bash
    sudo -u postgres psql -c "create user sbe with encrypted password 'a-password';"
    sudo -u postgres psql -c "create database sbe owner sbe;"
    ```

    and in `.env`:

    ```bash
    FLASK_SQLALCHEMY_DATABASE_URI="postgresql://sbe:a-password@localhost/sbe"
    ```

=== "MariaDB"

    ```bash
    sudo mariadb -e "
      CREATE DATABASE sbe CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
      CREATE USER 'sbe'@'localhost' IDENTIFIED BY 'a-password';
      GRANT ALL PRIVILEGES ON sbe.* TO 'sbe'@'localhost';"
    ```

    and in `.env`:

    ```bash
    FLASK_SQLALCHEMY_DATABASE_URI="mysql+pymysql://sbe:a-password@localhost/sbe?charset=utf8mb4"
    ```

## Configuration

Copy `example_config/dot_env` to `.env` and fill it in: the secret key, the database, Redis, the server name, e-mail. [Configuration](configuration.md) lists every setting.

## First start

These commands are needed once, to create the tables and the first administrator:

```bash
flask initdb
flask createuser --role admin --name "Ada Lovelace" ada@example.org a-password
```

For a site moved from another server, restore its database instead, copy its files into `src/instance/data/files` (or the `FLASK_INSTANCE_PATH` you set), then run `flask db upgrade` and `flask reindex`.

## Running

The application runs as three processes, listed in the repository's `Procfile`:

```
worker: flask worker
scheduler: flask scheduler
web: gunicorn abilian.wsgi:app -b 0.0.0.0:${PORT:-8000} --workers 4 --log-level info --log-file -
```

Start them with `honcho start` (from `uv run`), or turn each line into a systemd service.

## nginx

nginx serves the site over HTTPS and passes requests to gunicorn: `example_config/sbe.example.com` is an example. Set its `client_max_body_size` to the largest file people will upload.

## Updating

```bash
git pull
uv sync --no-dev --extra postgres
make front translations
flask db upgrade
```

Then restart the three processes.
