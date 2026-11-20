# Sur un serveur

Ce guide installe Abilian SBE sur un serveur Debian ou Ubuntu, nommé ici `sbe.example.org`, derrière nginx. Le dossier `example_config/` du dépôt contient les fichiers d'exemple auxquels il renvoie.

## Un utilisateur dédié

```bash
sudo useradd -m -s /bin/bash sbe
sudo su - sbe
```

## Paquets système

```bash
sudo apt install build-essential git curl redis-server \
    poppler-utils imagemagick libreoffice-nogui \
    postgresql libpq-dev        # ou : mariadb-server
```

Ajoutez `clamav-daemon` pour analyser les fichiers déposés, ainsi que `nginx` et `certbot` pour le serveur web. Node et npm ne servent qu'à construire les scripts des pages à partir d'une copie des sources.

## uv et l'application

Abilian SBE utilise [uv](https://docs.astral.sh/uv/) pour gérer Python et ses dépendances. Il lui faut Python 3.12 ou plus récent, que uv télécharge si le système ne l'a pas.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone --depth 1 --branch main https://github.com/abilian/abilian-sbe-monorepo.git
cd abilian-sbe-monorepo
uv sync --no-dev --extra postgres
make front translations
```

`make front` construit les scripts des pages avec Vite (il lance `npm install` dans `vite/`) ; `make translations` compile les traductions. Les commandes qui suivent supposent l'environnement de uv : préfixez-les par `uv run`, ou activez-le avec `. .venv/bin/activate`.

## La base de données

=== "PostgreSQL"

    ```bash
    sudo -u postgres psql -c "create user sbe with encrypted password 'a-password';"
    sudo -u postgres psql -c "create database sbe owner sbe;"
    ```

    et dans `.env` :

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

    et dans `.env` :

    ```bash
    FLASK_SQLALCHEMY_DATABASE_URI="mysql+pymysql://sbe:a-password@localhost/sbe?charset=utf8mb4"
    ```

## Configuration

Copiez `example_config/dot_env` vers `.env` et remplissez-le : la clé secrète, la base de données, Redis, le nom du serveur, l'e-mail. [Configuration](configuration.md) liste tous les paramètres.

## Premier démarrage

Ces commandes ne servent qu'une fois, pour créer les tables et le premier administrateur :

```bash
flask initdb
flask createuser --role admin --name "Ada Lovelace" ada@example.org a-password
```

Pour un site venu d'un autre serveur, restaurez plutôt sa base de données, copiez ses fichiers dans `src/instance/data/files` (ou dans le `FLASK_INSTANCE_PATH` que vous avez défini), puis lancez `flask db upgrade` et `flask reindex`.

## Exécution

L'application tourne sous la forme de trois processus, listés dans le `Procfile` du dépôt :

```
worker: flask worker
scheduler: flask scheduler
web: gunicorn abilian.wsgi:app -b 0.0.0.0:${PORT:-8000} --workers 4 --log-level info --log-file -
```

Démarrez-les avec `honcho start` (via `uv run`), ou faites de chaque ligne un service systemd.

## nginx

nginx sert le site en HTTPS et transmet les requêtes à gunicorn : `example_config/sbe.example.com` en donne un exemple. Réglez son `client_max_body_size` sur la taille du plus gros fichier que les utilisateurs déposeront.

## Mise à jour

```bash
git pull
uv sync --no-dev --extra postgres
make front translations
flask db upgrade
```

Redémarrez ensuite les trois processus.
