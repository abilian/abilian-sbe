# Full installation example

Installation on a Ubuntu Linux bare-metal server. The server name is "sbe.example.com".

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
    python-dev
    libpq-dev
    libxslt1-dev
    libjpeg-dev
    libffi-dev
    libsqlite3-dev
    libbz2-dev
    postgresql
    redis
    poppler-utils
    imagemagick
    libreoffice
    clamav
    nodejs
    npm
    honcho
    curl

Optional (if using Nginx and Letsencrypt like service):

    nginx
    certbot


# Create a Python virtual env (Python version 3.12)

```bash
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-dev python3.12-venv
```


### Installation of `pip` from sources:

```bash
sudo curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12
```

### Virtual environment named "venv":

```bash
python3.12 -m venv venv
. venv/bin/activate
```

## Clone SBE source code and install

```bash
git clone --depth 1  --branch main https://github.com/abilian/abilian-sbe-monorepo.git
cd abilian-sbe-monorepo
pip install -U pip setuptools poetry
pip install .
```

## Create a Postgresql database (here named "sbe")

```bash
sudo -u postgres psql
create database sbe;
create user sbe with encrypted password 'sbe';
grant all privileges on database sbe to sbe;
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
Expected result: `lessc 4.2.0 (Less Compiler) [JavaScript]`

## Nginx proxy

If using Nginx, check you have configured `nginx` with relevant SSL keys. See example file `sbe.example.com` in this directory.

Note: The example `nginx` configuration contains a permanent redirect for some static web resources. This can be adapted to the actual site configuration for static files. The other parts of the setup are otherwise pretty standard.

```
location ~ ^/static/min/abilian/web/resources/(.*) {
    		return 301 /static/abilian/$1 ;
        }
```

## Create a local '.env' file

See 'dot_env' file in this directory. Of course `FLASK_*` variables can be declared using other Flask configuration methods.

## First initialization of SBE application

This commands are required only once:

```bash
flask assets build
flask initdb
flask createuser --role admin --name admin admin@example.com   # asks for the password
```

## Start the SBE application

Create a local `Procfile` containing those lines (adapt the `gunicorn` configuration)

```
worker: flask worker
scheduler: flask scheduler
web: gunicorn extranet.wsgi:app -b :8000 --workers 4 --log-file -
```

And finally start the application using `honcho`:

```bash
honcho -f Procfile start
```
