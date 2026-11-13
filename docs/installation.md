# Full Installation Guide

This guide provides a detailed walkthrough for installing software on a Ubuntu Linux server.

The following instructions are tailored for a bare-metal server setup, specifically for a server named "sbe.example.com."

(For cloud installations, the `cloud/` folder contains configuration examples for Docker, Nua, SlapOS and Vagrant.)

## Create a dedicated user

A user "sbe" with `sudoer` rights.

```bash
sudo useradd -m -s /bin/bash -G sudo sbe
sudo su - sbe
```

## Packages requirements

List of packages to install with `apt`:

    default-jre
    libreoffice-java-common
    build-essential
    libpq-dev
    libxslt1-dev
    libjpeg-dev
    libffi-dev
    libsqlite3-dev
    libbz2-dev
    postgresql
    mariadb-server
    redis
    poppler-utils
    imagemagick
    libreoffice
    clamav
    nodejs
    npm
    honcho
    curl

`libpq-dev` is only needed with PostgreSQL, `mariadb-server` only with MariaDB.

The `clamav` package only enables virus scanning if the optional `clamd` Python package is also installed (`uv add clamd`); otherwise scanning is silently skipped.

Optional (if using Nginx and Letsencrypt like service):

    nginx
    certbot


## Install `uv`

SBE uses [uv](https://docs.astral.sh/uv/) to manage Python and its dependencies. It requires Python 3.13, which `uv` downloads automatically if the system doesn't provide it.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Clone SBE source code and install

```bash
git clone --depth 1 --branch main https://github.com/abilian/abilian-sbe-monorepo.git
cd abilian-sbe-monorepo
uv sync --no-dev
. .venv/bin/activate
```

The commands below assume this virtual env is active (or prefix them with `uv run`).

## Create a PostgreSQL database (here named "sbe")

The PostgreSQL driver is no longer a default dependency, add it first:

```bash
uv add psycopg2-binary
```

Then create the database:

```bash
sudo -u postgres psql
create database sbe;
create user sbe with encrypted password 'sbe';
grant all privileges on database sbe to sbe;
```

And configure the SQLAlchemy URI in `.env`:

```bash
FLASK_SQLALCHEMY_DATABASE_URI="postgresql://sbe:sbe@localhost:5432/sbe"
```

## Or create a MariaDB database (here named "sbe")

On Linux (as `root` / `sudo mariadb`):

```bash
sudo mariadb -e "
  CREATE DATABASE IF NOT EXISTS sbe CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE OR REPLACE USER 'sbe'@'localhost' IDENTIFIED BY 'sbe';
  CREATE OR REPLACE USER 'sbe'@'127.0.0.1' IDENTIFIED BY 'sbe';
  GRANT ALL PRIVILEGES ON sbe.* TO 'sbe'@'localhost';
  GRANT ALL PRIVILEGES ON sbe.* TO 'sbe'@'127.0.0.1';
"
```

To run the tests against MariaDB without installing it, use `make test-mariadb-docker`: it runs the database and the tests in containers (see `tests/docker/`).

On macOS (Homebrew `mariadb`), or to create the `sbe_test` database for `make test-mariadb`:

```bash
mariadb -u "$USER" -e "
  CREATE DATABASE IF NOT EXISTS sbe_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE OR REPLACE USER 'sbe'@'localhost' IDENTIFIED BY 'sbe';
  CREATE OR REPLACE USER 'sbe'@'127.0.0.1' IDENTIFIED BY 'sbe';
  GRANT ALL PRIVILEGES ON sbe_test.* TO 'sbe'@'localhost';
  GRANT ALL PRIVILEGES ON sbe_test.* TO 'sbe'@'127.0.0.1';
"
```

Then configure the SQLAlchemy URI in `.env`:

```bash
FLASK_SQLALCHEMY_DATABASE_URI="mysql+pymysql://sbe:sbe@127.0.0.1/sbe?charset=utf8mb4"
```

## Start services if necessary
```bash
sudo systemctl start clamav-freshclam
sudo systemctl start clamav-daemon
sudo systemctl start redis
```

## If needed, create a few directories

### Maildir:

```bash
mkdir -p "${HOME}"/Maildir/{cur,new,tmp}
chmod 0700 "${HOME}"/Maildir/{cur,new,tmp}
```

### Local flask instance:

This should be created by Flask at first start, however in the `abilian-sbe-monorepo` directory:

```bash
mkdir -p ./src/instance
```

## Node.js packages

From `abilian-sbe-monorepo` directory:

```bash
npm install --verbose
```

Check that `lessc` is now available (or edit the related `Flask` config variable for the actual path):

```bash
./node_modules/.bin/lessc --version
```
Expected result: `lessc 4.x (Less Compiler) [JavaScript]`

## Nginx proxy

If using Nginx, check you have configured `nginx` with relevant SSL keys. See the example file `example_config/sbe.example.com`.

Note: The example `nginx` configuration contains a permanent redirect for some static web resources. This can be adapted to the actual site configuration for static files. The other parts of the setup are otherwise pretty standard.

```
location ~ ^/static/min/abilian/web/resources/(.*) {
    		return 301 /static/abilian/$1 ;
        }
```

## Create a local '.env' file

See the example file `example_config/dot_env`. Of course `FLASK_*` variables can be declared using other Flask configuration methods.

## First initialization of SBE application

These commands are required only once:

```bash
flask assets build
flask initdb
flask createuser --role admin --name admin admin@example.com some_password
```

## Start the SBE application

Create a local `Procfile` containing those lines (adapt the `gunicorn` configuration)

```
worker: flask worker
scheduler: flask scheduler
web: gunicorn wsgi:app -b :8000 --workers 4 --log-file -
```

And finally start the application using `honcho`:

```bash
honcho -f Procfile start
```
