# Sur Hop3

[Hop3](https://hop3.cloud/) construit une application à partir de ses sources, exécute ses processus et fournit sa base de données et son Redis. Le dépôt contient une configuration prête à l'emploi, `hop3.toml`.

## Le rôle de la configuration

- **Elle construit** l'application Python avec uv et les scripts des pages avec Node et Vite.
- **Elle exécute** l'application web sous gunicorn, le *worker* et l'ordonnanceur.
- **Avant chaque démarrage**, elle compile les traductions, met à jour le schéma de la base de données (`flask db upgrade`) et lance les reprises de données.
- **Elle fournit** une base PostgreSQL et un Redis, dont elle transmet les adresses à l'application.
- **Elle conserve** l'instance (fichiers, index de recherche, caches) sur un volume, qu'un nouveau déploiement laisse en place.
- **Elle installe** Poppler, ImageMagick et LibreOffice, pour les aperçus et la recherche dans les documents.
- **Elle génère** la clé secrète lors du premier déploiement.

## Avant le premier déploiement

Indiquez le domaine du site dans la section `[domains]` de `hop3.toml`, puis les paramètres secrets, que la configuration laisse de côté volontairement :

```bash
hop3 env set --app extranet-cnll FLASK_MAIL_SERVER=smtp.example.org
hop3 env set --app extranet-cnll FLASK_MAIL_USERNAME=… FLASK_MAIL_PASSWORD=…
hop3 env set --app extranet-cnll FLASK_MAIL_SENDER=extranet@example.org
```

Remplacez `extranet-cnll` par le nom de votre application, l'`id` de la section `[metadata]`. Le nom du site (`FLASK_SITE_NAME`) et ses langues se trouvent dans la section `[env]`.

## Déployer

Depuis le dépôt :

```bash
hop3 deploy
```

Créez ensuite le premier administrateur en lançant cette commande dans l'environnement de l'application (`hop3 help` indique comment y lancer une commande) :

```bash
flask createuser --role admin --name "Ada Lovelace" ada@example.org a-password
```

## Déplacer un site existant

Restaurez une sauvegarde de l'ancienne base de données dans la base Hop3, copiez l'ancien dossier `data/files` dans le dossier `data/files` du volume, puis déployez : le schéma est mis à jour avant le démarrage de l'application. Lancez ensuite `flask reindex` une fois, pour reconstruire l'index de recherche.
