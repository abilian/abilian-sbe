# On Hop3

[Hop3](https://hop3.cloud/) builds an application from its source, runs its processes and provides its database and its Redis. The repository holds a ready configuration, `hop3.toml`.

## What the configuration does

- **Builds** the Python application with uv, and the pages' scripts with Node and Vite.
- **Runs** the web application under gunicorn, the worker and the scheduler.
- **Before each start**, compiles the translations, brings the database schema up to date (`flask db upgrade`) and runs the data backfills.
- **Provides** a PostgreSQL database and a Redis, and hands their addresses to the application.
- **Keeps** the instance (files, search index, caches) on a volume, which a new deployment leaves in place.
- **Installs** Poppler, ImageMagick and LibreOffice, for previews and search inside documents.
- **Generates** the secret key on the first deployment.

## Before the first deployment

Set the site's domain in `[domains]` of `hop3.toml`. Then set the settings that are secrets, which the configuration leaves out on purpose:

```bash
hop3 env set --app extranet-cnll FLASK_MAIL_SERVER=smtp.example.org
hop3 env set --app extranet-cnll FLASK_MAIL_USERNAME=… FLASK_MAIL_PASSWORD=…
hop3 env set --app extranet-cnll FLASK_MAIL_SENDER=extranet@example.org
```

Replace `extranet-cnll` by your application's name, the `id` of `[metadata]`. The site's name (`FLASK_SITE_NAME`) and its languages are in the `[env]` section.

## Deploying

From the repository:

```bash
hop3 deploy
```

Then create the first administrator, by running this command in the application's environment (`hop3 help` shows how to run a command there):

```bash
flask createuser --role admin --name "Ada Lovelace" ada@example.org a-password
```

## Moving an existing site

Restore a dump of the old database into the Hop3 database, copy the old `data/files` folder into the volume's `data/files`, and deploy: the schema is brought up to date before the application starts. Then run `flask reindex` once, to rebuild the search index.
