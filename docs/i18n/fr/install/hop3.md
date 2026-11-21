# Sur Hop3

[Hop3](https://hop3.cloud/) exécute les processus d'une application et lui fournit sa base de données et son Redis. Un site déployé sur Hop3 est un petit projet à part, sans code : un fichier fixe la version d'Abilian SBE, prise sur PyPI, et un autre indique comment l'exécuter. Le paquet contient tout ce dont l'application a besoin : ses scripts, ses traductions compilées et ses migrations.

## Le projet

`pyproject.toml` :

```toml
[project]
name = "mon-extranet"
version = "1.0"
requires-python = ">=3.12"
dependencies = ["abilian-sbe[postgres]==2.0.0"]
```

Lancez `uv lock` pour écrire `uv.lock`, qui fixe la version de chaque dépendance.

`hop3.toml` nomme votre application et son domaine :

```toml
[metadata]
id = "mon-extranet"

[domains]
list = ["extranet.example.org"]

[run]
# Avant chaque démarrage : les tables créées au premier, puis tenues à jour.
before-run = ["flask preparedb"]
start = "gunicorn abilian.wsgi:app -b 0.0.0.0:$PORT --workers 4 --log-file -"
start-timeout = 180
# Pour les aperçus et la recherche dans les documents.
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

# Les fichiers, l'index de recherche et les caches, qu'un nouveau déploiement conserve.
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
FLASK_SITE_NAME = "Mon extranet"
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

Déclarer les modules PostgreSQL et Redis suffit à transmettre leurs adresses à l'application, `DATABASE_URL` et `REDIS_URL`. La page [Configuration](configuration.md) liste les autres paramètres.

## Avant le premier déploiement

Définissez les paramètres secrets, que `hop3.toml` laisse de côté volontairement :

```bash
hop3 env set --app mon-extranet FLASK_MAIL_SERVER=smtp.example.org
hop3 env set --app mon-extranet FLASK_MAIL_USERNAME=… FLASK_MAIL_PASSWORD=…
hop3 env set --app mon-extranet FLASK_MAIL_SENDER=extranet@example.org
```

## Déployer

Depuis le projet :

```bash
hop3 deploy
```

Le premier démarrage crée les tables. Créez ensuite le premier administrateur, dans l'environnement de l'application :

```bash
hop3 run --app mon-extranet flask createuser --role admin --name "Ada Lovelace" ada@example.org a-password
```

## Mettre à jour

Changez la version d'`abilian-sbe` dans `pyproject.toml`, lancez `uv lock`, puis déployez : les migrations s'exécutent avant le démarrage de l'application.

## Déplacer un site existant

Videz la base créée par Hop3, importez-y une sauvegarde de l'ancienne (`hop3 addon postgres import`), copiez l'ancien dossier `data/files` dans le dossier `data/files` du volume, puis redéployez : `flask preparedb` trouve les anciennes tables et les met à jour. Lancez ensuite `flask reindex` une fois, pour reconstruire l'index de recherche.
