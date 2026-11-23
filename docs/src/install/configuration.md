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
| `FLASK_PRODUCTION` | `true` in production: the daily summary is sent only then (see [Daily summary](#daily-summary)). |

## E-mail

| Variable | What it sets |
|---|---|
| `FLASK_MAIL_SERVER`, `FLASK_MAIL_PORT` | The SMTP server, and its port (25 by default). |
| `FLASK_MAIL_USE_TLS`, `FLASK_MAIL_USE_SSL` | How to reach it. |
| `FLASK_MAIL_USERNAME`, `FLASK_MAIL_PASSWORD` | Its credentials. |
| `FLASK_MAIL_SENDER` | The address e-mails are sent from. |
| `FLASK_BULK_MAIL_SENDER` | The address of the e-mails sent to many: forum posts and the daily summary. `FLASK_MAIL_SENDER` by default. |
| `FLASK_MAIL_SUPPRESS_SEND` | `true` sends no e-mail at all; the administration's health page says so. |

## Replies by e-mail

A forum post sent by e-mail can be answered by e-mail: the reply is posted in the thread.

| Variable | What it sets |
|---|---|
| `FLASK_SBE_FORUM_REPLY_BY_MAIL` | `true` lets members reply to a forum e-mail. `false` by default. |
| `FLASK_SBE_FORUM_REPLY_ADDRESS` | The address the forum e-mails come from, `forum@extranet.example.org`. Each e-mail is answered to a variant of it, `forum+…@extranet.example.org`, that names the thread and the member: the mail server must deliver those to the same mailbox. `FLASK_BULK_MAIL_SENDER` by default. |
| `FLASK_INCOMING_MAIL_USE_MAILDIR` | `true` when the replies are delivered to the `~/Maildir` of the user the worker runs as: it is then checked every minute (`FLASK_SCHEDULE_CHECK_MAILDIR`, a cron line). Otherwise, the mail server hands each reply to `flask inject_email`, on its standard input. |

## Daily summary

| Variable | What it sets |
|---|---|
| `FLASK_PRODUCTION` | The summary is sent only when it is `true`. |
| `FLASK_DEMO` | `true` on a demonstration site: no summary, even in production. |
| `FLASK_ABILIAN_SBE__DAILY_SOCIAL_DIGEST_SUBJECT` | The subject of the summary, "Des nouvelles de vos communautés" by default. The double underscore is not a typo: the setting is `DAILY_SOCIAL_DIGEST_SUBJECT` within `ABILIAN_SBE`. |

## Site

| Variable | What it sets |
|---|---|
| `FLASK_PRIVATE_SITE` | `true` asks every visitor to sign in, on every page. |
| `FLASK_BABEL_ACCEPT_LANGUAGES` | The languages offered, for instance `["fr", "en"]`; the first is the default. |
| `FLASK_INSTANCE_PATH` | Where the instance lives: files, search index, caches. Relative to where the application starts. |
| `FLASK_SENTRY_DSN` | Reports errors to Sentry. |
| `FLASK_ENABLE_CALENDAR` | `false` takes the calendar out of every community. `true` by default. |
| `FLASK_WHOOSH_BASE` | Where the search index is kept: `whoosh` by default, in the instance folder when the path is relative. |
| `FLASK_ANTIVIRUS_CHECK_REQUIRED` | `true` holds back a document's content (download, preview, sending) until the antivirus has found it clean. `false` by default: only a document found infected is held back. |
| `FLASK_SBE_LOCK_LIFETIME` | How long, in seconds, a document stays locked by whoever is editing it: 3600 by default. |
| `FLASK_WTF_CSRF_TIME_LIMIT` | How long, in seconds, a form stays valid once shown: 3600 by default. A form sent later is refused. |
| `FLASK_FILE_UPLOADS__DELETE_STALLED_AFTER` | How long, in seconds, a file uploaded with a form that was never sent is kept: a day by default. |

Some settings are also edited from the administration (**Settings**): the site's name, the sender's address and the hour of the daily summary. A value saved there takes precedence over the environment, from the next start of each process.
