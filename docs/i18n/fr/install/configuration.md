# Configuration

Abilian SBE lit ses paramètres dans des variables d'environnement dont le nom commence par `FLASK_` : `FLASK_SITE_NAME` définit `SITE_NAME`. En développement, placez-les dans un fichier `.env` à la racine du dépôt ; `example_config/dot_env` sert de point de départ. Une valeur est lue comme du JSON quand c'est possible : `true`, `25` et `["fr", "en"]` sont donc un booléen, un nombre et une liste.

## L'essentiel

| Variable | Ce qu'elle définit |
|---|---|
| `FLASK_SECRET_KEY` | La clé qui signe les sessions et les liens. Une longue chaîne aléatoire, à garder secrète. |
| `FLASK_SQLALCHEMY_DATABASE_URI` | La base de données, par exemple `postgresql://sbe:…@localhost/sbe` ou `mysql+pymysql://sbe:…@127.0.0.1/sbe?charset=utf8mb4`. |
| `FLASK_REDIS_URI` | Redis, par exemple `redis://localhost:6379/0`. |
| `FLASK_DRAMATIQ_BROKER_URL` | La file de tâches : la même adresse Redis. |
| `FLASK_SERVER_NAME` | Le nom d'hôte du site, `extranet.example.org`. Les liens des e-mails sont construits à partir de lui. |
| `FLASK_SITE_NAME` | Le nom affiché dans la barre et dans les e-mails. |
| `FLASK_PRODUCTION` | `true` en production : le résumé quotidien n'est envoyé que dans ce cas. |

## E-mail

| Variable | Ce qu'elle définit |
|---|---|
| `FLASK_MAIL_SERVER`, `FLASK_MAIL_PORT` | Le serveur SMTP et son port (25 par défaut). |
| `FLASK_MAIL_USE_TLS`, `FLASK_MAIL_USE_SSL` | La façon de s'y connecter. |
| `FLASK_MAIL_USERNAME`, `FLASK_MAIL_PASSWORD` | Ses identifiants. |
| `FLASK_MAIL_SENDER` | L'adresse d'expédition des e-mails. |

## Site

| Variable | Ce qu'elle définit |
|---|---|
| `FLASK_PRIVATE_SITE` | `true` demande à chaque visiteur de se connecter, sur chaque page. |
| `FLASK_BABEL_ACCEPT_LANGUAGES` | Les langues proposées, par exemple `["fr", "en"]` ; la première est celle par défaut. |
| `FLASK_INSTANCE_PATH` | L'emplacement de l'instance : fichiers, index de recherche, caches. Relatif au répertoire où démarre l'application. |
| `FLASK_SENTRY_DSN` | Envoie les erreurs à Sentry. |

Certains paramètres se modifient aussi depuis l'administration (**Paramètres**) : le nom du site, l'adresse de l'expéditeur et l'heure du résumé quotidien. Une valeur enregistrée là l'emporte sur l'environnement, à partir du prochain démarrage de chaque processus.
