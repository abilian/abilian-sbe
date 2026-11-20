# Configuration

Abilian SBE reads its settings from environment variables whose names start with `FLASK_`: `FLASK_SITE_NAME` sets `SITE_NAME`. In development, put them in a `.env` file at the root of the repository; `example_config/dot_env` is a starting point. A value is read as JSON when it can be, so `true`, `25` and `["fr", "en"]` are a boolean, a number and a list.

## Essential

| Variable | What it sets |
|---|---|
| `FLASK_SECRET_KEY` | The key that signs sessions and links. Long, random and secret. |
| `FLASK_SQLALCHEMY_DATABASE_URI` | The database, for instance `postgresql://sbe:…@localhost/sbe` or `mysql+pymysql://sbe:…@127.0.0.1/sbe?charset=utf8mb4`. |
| `FLASK_REDIS_URI` | Redis, for instance `redis://localhost:6379/0`. |
| `FLASK_DRAMATIQ_BROKER_URL` | The task queue: the same Redis address. |
| `FLASK_SERVER_NAME` | The site's host name, `extranet.example.org`. The links in e-mails are built from it. |
| `FLASK_SITE_NAME` | The name shown in the bar and in e-mails. |
| `FLASK_PRODUCTION` | `true` in production: the daily summary is sent only then. |

## E-mail

| Variable | What it sets |
|---|---|
| `FLASK_MAIL_SERVER`, `FLASK_MAIL_PORT` | The SMTP server, and its port (25 by default). |
| `FLASK_MAIL_USE_TLS`, `FLASK_MAIL_USE_SSL` | How to reach it. |
| `FLASK_MAIL_USERNAME`, `FLASK_MAIL_PASSWORD` | Its credentials. |
| `FLASK_MAIL_SENDER` | The address e-mails are sent from. |

## Site

| Variable | What it sets |
|---|---|
| `FLASK_PRIVATE_SITE` | `true` asks every visitor to sign in, on every page. |
| `FLASK_BABEL_ACCEPT_LANGUAGES` | The languages offered, for instance `["fr", "en"]`; the first is the default. |
| `FLASK_INSTANCE_PATH` | Where the instance lives: files, search index, caches. Relative to where the application starts. |
| `FLASK_SENTRY_DSN` | Reports errors to Sentry. |

Some settings are also edited from the administration (**Settings**): the site's name, the sender's address and the hour of the daily summary. A value saved there takes precedence over the environment, from the next start of each process.
