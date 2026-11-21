# Copyright (c) 2012-2024, Abilian SAS

"""A new database is made at the latest migration, and says so.

Left unmarked, the next upgrade replays every migration over tables that
exist. `flask preparedb`, which runs before each start, makes a database when
there is none and migrates the one there is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from abilian.cli.base import initdb, preparedb
from abilian.setup.extensions import MIGRATIONS_DIR

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy


def test_initdb_marks_the_database_at_the_latest_migration(
    app: Application, db: SQLAlchemy
) -> None:
    result = app.test_cli_runner().invoke(initdb)

    assert result.exit_code == 0, result.output
    assert current_revision(db) == head_revision()


def test_preparedb_creates_an_empty_database(app: Application, db: SQLAlchemy) -> None:
    db.drop_all()
    with db.engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))

    result = app.test_cli_runner().invoke(preparedb)

    assert result.exit_code == 0, result.output
    assert "community" in sa.inspect(db.engine).get_table_names()
    assert current_revision(db) == head_revision()


def test_preparedb_migrates_an_existing_database(
    app: Application, db: SQLAlchemy
) -> None:
    runner = app.test_cli_runner()
    runner.invoke(initdb)

    result = runner.invoke(preparedb)

    assert result.exit_code == 0, result.output
    assert current_revision(db) == head_revision()


def current_revision(db: SQLAlchemy) -> str | None:
    with db.engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def head_revision() -> str | None:
    return ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head()
