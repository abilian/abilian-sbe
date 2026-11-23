"""An event's columns at the types of the model.

The first migration made `title`, `description`, `location` and `url`
unbounded `VARCHAR`s; the model, which `flask initdb` creates the tables from,
has `title` as `VARCHAR(255)` and the others as `TEXT`. A database made by the
migrations now has the model's types too.

Revision ID: 9e4f1a2b3c5d
Revises: 8d2e0f4a5b3c
Create Date: 2026-11-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "9e4f1a2b3c5d"
down_revision = "8d2e0f4a5b3c"
branch_labels = None
depends_on = None

TITLE_LENGTH = 255
TEXT_COLUMNS = ("description", "location", "url")


def upgrade() -> None:
    # A longer title would fail the change of type on PostgreSQL, and be cut
    # anyway, without a word, by MySQL and MariaDB.
    event = sa.table("sbe_event", sa.column("title", sa.Unicode()))
    op.execute(
        event.update()
        .where(sa.func.length(event.c.title) > TITLE_LENGTH)
        .values(title=sa.func.substr(event.c.title, 1, TITLE_LENGTH))
    )
    # Batch mode: SQLite changes a type only by recreating the table. MySQL
    # and MariaDB restate the whole column, nullability included.
    with op.batch_alter_table("sbe_event") as batch:
        batch.alter_column(
            "title",
            type_=sa.Unicode(TITLE_LENGTH),
            existing_type=sa.Unicode(),
            existing_nullable=False,
        )
        for name in TEXT_COLUMNS:
            batch.alter_column(
                name,
                type_=sa.UnicodeText(),
                existing_type=sa.Unicode(),
                existing_nullable=False,
            )


def downgrade() -> None:
    # MySQL and MariaDB have no VARCHAR without a length: there, the first
    # migration could not run, and the tables always had the model's types.
    if op.get_bind().dialect.name in ("mysql", "mariadb"):
        return
    with op.batch_alter_table("sbe_event") as batch:
        batch.alter_column(
            "title",
            type_=sa.Unicode(),
            existing_type=sa.Unicode(TITLE_LENGTH),
            existing_nullable=False,
        )
        for name in TEXT_COLUMNS:
            batch.alter_column(
                name,
                type_=sa.Unicode(),
                existing_type=sa.UnicodeText(),
                existing_nullable=False,
            )
