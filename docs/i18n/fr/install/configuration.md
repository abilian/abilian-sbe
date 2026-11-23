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
| `FLASK_PRODUCTION` | `true` en production : le résumé quotidien n'est envoyé que dans ce cas (voir [Résumé quotidien](#resume-quotidien)). |

## E-mail

| Variable | Ce qu'elle définit |
|---|---|
| `FLASK_MAIL_SERVER`, `FLASK_MAIL_PORT` | Le serveur SMTP et son port (25 par défaut). |
| `FLASK_MAIL_USE_TLS`, `FLASK_MAIL_USE_SSL` | La façon de s'y connecter. |
| `FLASK_MAIL_USERNAME`, `FLASK_MAIL_PASSWORD` | Ses identifiants. |
| `FLASK_MAIL_SENDER` | L'adresse d'expédition des e-mails. |
| `FLASK_BULK_MAIL_SENDER` | L'adresse d'expédition des e-mails envoyés en nombre : messages du forum et résumé quotidien. `FLASK_MAIL_SENDER` par défaut. |
| `FLASK_MAIL_SUPPRESS_SEND` | `true` n'envoie aucun e-mail ; la page d'état de l'administration le signale. |

## Réponses par e-mail

Un message du forum envoyé par e-mail peut recevoir une réponse par e-mail : elle est publiée dans la discussion.

| Variable | Ce qu'elle définit |
|---|---|
| `FLASK_SBE_FORUM_REPLY_BY_MAIL` | `true` permet aux membres de répondre à un e-mail du forum. `false` par défaut. |
| `FLASK_SBE_FORUM_REPLY_ADDRESS` | L'adresse d'où partent les e-mails du forum, `forum@extranet.example.org`. On répond à chacun à une variante de cette adresse, `forum+…@extranet.example.org`, qui désigne la discussion et le membre : le serveur de messagerie doit les remettre dans la même boîte. `FLASK_BULK_MAIL_SENDER` par défaut. |
| `FLASK_INCOMING_MAIL_USE_MAILDIR` | `true` quand les réponses arrivent dans le `~/Maildir` de l'utilisateur sous lequel tourne le worker : il est alors relevé chaque minute (`FLASK_SCHEDULE_CHECK_MAILDIR`, une ligne cron). Sinon, le serveur de messagerie passe chaque réponse à `flask inject_email`, sur son entrée standard. |

## Résumé quotidien

| Variable | Ce qu'elle définit |
|---|---|
| `FLASK_PRODUCTION` | Le résumé n'est envoyé que si elle vaut `true`. |
| `FLASK_DEMO` | `true` sur un site de démonstration : pas de résumé, même en production. |
| `FLASK_ABILIAN_SBE__DAILY_SOCIAL_DIGEST_SUBJECT` | L'objet du résumé, « Des nouvelles de vos communautés » par défaut. Le double tiret bas n'est pas une coquille : le paramètre est `DAILY_SOCIAL_DIGEST_SUBJECT`, dans `ABILIAN_SBE`. |

## Site

| Variable | Ce qu'elle définit |
|---|---|
| `FLASK_PRIVATE_SITE` | `true` demande à chaque visiteur de se connecter, sur chaque page. |
| `FLASK_BABEL_ACCEPT_LANGUAGES` | Les langues proposées, par exemple `["fr", "en"]` ; la première est celle par défaut. |
| `FLASK_INSTANCE_PATH` | L'emplacement de l'instance : fichiers, index de recherche, caches. Relatif au répertoire où démarre l'application. |
| `FLASK_SENTRY_DSN` | Envoie les erreurs à Sentry. |
| `FLASK_ENABLE_CALENDAR` | `false` retire l'agenda de toutes les communautés. `true` par défaut. |
| `FLASK_WHOOSH_BASE` | L'emplacement de l'index de recherche : `whoosh` par défaut, dans le dossier de l'instance quand le chemin est relatif. |
| `FLASK_ANTIVIRUS_CHECK_REQUIRED` | `true` retient le contenu d'un document (téléchargement, aperçu, envoi) tant que l'antivirus ne l'a pas trouvé sain. `false` par défaut : seul un document trouvé infecté est retenu. |
| `FLASK_SBE_LOCK_LIFETIME` | La durée, en secondes, pendant laquelle un document reste verrouillé par la personne qui le modifie : 3600 par défaut. |
| `FLASK_WTF_CSRF_TIME_LIMIT` | La durée, en secondes, pendant laquelle un formulaire affiché reste valable : 3600 par défaut. Envoyé plus tard, il est refusé. |
| `FLASK_FILE_UPLOADS__DELETE_STALLED_AFTER` | La durée, en secondes, de conservation d'un fichier déposé dans un formulaire jamais envoyé : un jour par défaut. |

Certains paramètres se modifient aussi depuis l'administration (**Paramètres**) : le nom du site, l'adresse de l'expéditeur et l'heure du résumé quotidien. Une valeur enregistrée là l'emporte sur l'environnement, à partir du prochain démarrage de chaque processus.
