# Developer guide

This section is for people who work on Abilian SBE itself. It is in English only.

## Setting up

You need [uv](https://docs.astral.sh/uv/), Node and npm, Redis, and for previews Poppler, ImageMagick and LibreOffice. PostgreSQL or MariaDB are optional: the tests run on SQLite by default.

```bash
git clone https://github.com/abilian/abilian-sbe-monorepo.git
cd abilian-sbe-monorepo
make install        # uv sync and the pre-commit hooks
make front translations
cp example_config/dot_env .env      # then edit it
uv run flask initdb
uv run flask createuser --role admin --name Admin admin@example.org   # asks for the password
make run            # the web server, Vite and Redis, through honcho
```

`make run` serves the site with Vite's development server, so a change to a script shows at once. Background tasks (conversions, e-mails, indexing) need the worker too: `uv run flask worker`, in another terminal.

## Where things are

- `src/abilian/core/`, `services/`, `web/`: the framework (Abilian Core): models, security, indexing, the administration.
- `src/abilian/sbe/apps/`: the applications: communities, documents, forum, wiki, calendar, social, preferences.
- `src/abilian/sbe/templates/` and `static/`: the pages, on the Abilian Design System (`static/ads/`, themed by `static/theme.css`).
- `vite/`: the pages' scripts.
- `src/abilian/migrations/`: the Alembic migrations, shipped in the package so that `flask db upgrade` runs from an installed SBE.
- `mockups/`: static mockups of every page, built by `uv run python mockups/build.py`.
- `notes/`: plans, decisions and the [Architecture Decision Records](https://github.com/abilian/abilian-sbe-monorepo/tree/main/notes/adrs).

## Releasing

`make dist` builds the scripts and the translations, then the sdist and the wheel in `dist/`, and checks that the wheel holds the scripts, the compiled translations and the migrations, and that neither package holds tests, notes or documentation.

## Testing

```bash
make test           # the pytest suite: unit, integration and end-to-end tiers
make test-e2e       # the browser tests (Playwright), including an accessibility sweep
make lint           # ruff, flake8, the dependency and import-contract checks
make test-postgres-docker   # the suite on PostgreSQL, in containers
make test-mariadb-docker    # the suite on MariaDB, in containers
```

`nox` runs the tests and linters in clean environments. The continuous integration runs on [SourceHut](https://builds.sr.ht/~sfermigier/abilian-sbe); its configuration is in `.builds/`.

## This documentation

The site is built with [Zensical](https://zensical.org/), from `docs/`: the English pages in `docs/src/`, the French ones in `docs/i18n/fr/`.

```bash
cd docs
make serve          # the English edition, live; `make serve EDITION=fr` for French
make check          # both editions, failing on a broken link
make shots          # the screenshots, from a throwaway instance with demo data
```

## Contributing

See [Contributing](contributing.md), the project's [Governance](governance.md) and its [Roadmap](roadmap.md).
