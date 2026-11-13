from __future__ import annotations

import nox

PYTHON_VERSIONS = ["3.13"]  # keep in sync with requires-python
DB_URIS = [
    "sqlite:///test.db",
    # TODO: Postgres & MariaDB
]
nox.options.reuse_existing_virtualenvs = True
nox.options.default_venv_backend = "uv|virtualenv"


@nox.session
def lint(session: nox.Session) -> None:
    uv_sync(session)
    session.run("uv", "pip", "check")
    session.run("uv", "run", "--active", "make", "lint")


# Not run in CI: bandit and `reuse lint` still report findings on the codebase.
@nox.session
def audit(session: nox.Session) -> None:
    uv_sync(session)
    session.run("uv", "pip", "install", "safety", "pip-audit", "bandit[toml]")
    session.run("uv", "run", "--active", "adt", "audit")


@nox.session(python=PYTHON_VERSIONS)
def pytest(session: nox.Session) -> None:
    uv_sync(session)
    session.run("uv", "run", "--active", "make", "test")


@nox.session
@nox.parametrize("db_uri", DB_URIS)
def db_test(session: nox.Session, db_uri: str) -> None:
    env = {
        "FLASK_SQLALCHEMY_DATABASE_URI": db_uri,
    }
    uv_sync(session)
    session.run("uv", "run", "--active", "pytest", "--tb=short", env=env)


def uv_sync(session: nox.Session):
    session.run("uv", "sync", "--active", external=True)
