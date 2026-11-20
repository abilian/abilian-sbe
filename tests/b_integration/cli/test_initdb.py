# Copyright (c) 2012-2024, Abilian SAS

"""A database made by `flask initdb` takes the next `flask db upgrade`.

It is made at the schema of the latest migration, so it has to say so: left
unmarked, the next upgrade replays every migration over tables that exist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from abilian.cli.base import initdb
from abilian.setup.extensions import MIGRATIONS_DIR

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy


def test_initdb_marks_the_database_at_the_latest_migration(
    app: Application, db: SQLAlchemy
) -> None:
    result = app.test_cli_runner().invoke(initdb)

    assert result.exit_code == 0, result.output
    with db.engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    assert current == ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head()
