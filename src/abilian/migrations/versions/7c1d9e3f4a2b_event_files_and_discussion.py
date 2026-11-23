"""An event's files, and the forum thread where it is discussed.

Revision ID: 7c1d9e3f4a2b
Revises: 5b2e8c41d7a3
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "7c1d9e3f4a2b"
down_revision = "5b2e8c41d7a3"
branch_labels = None
depends_on = None


# Batch mode: SQLite cannot add or drop a constraint but by recreating the
# table, which batch mode does there; elsewhere it emits plain ALTERs.


def upgrade() -> None:
    with op.batch_alter_table("sbe_event") as batch:
        batch.add_column(sa.Column("thread_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "sbe_event_thread_id_fkey",
            "forum_thread",
            ["thread_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("cmisobject") as batch:
        batch.add_column(sa.Column("_event_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "cmisobject__event_id_fkey", "sbe_event", ["_event_id"], ["id"]
        )


def downgrade() -> None:
    drop_column_and_foreign_key("cmisobject", "_event_id")
    drop_column_and_foreign_key("sbe_event", "thread_id")


def drop_column_and_foreign_key(table: str, column: str) -> None:
    """Drop `column` of `table`, and the foreign key on it, whatever its name.

    The name is looked up: on tables `flask initdb` made, the database chose
    it, a name of its own on MySQL and MariaDB, none at all on SQLite (where
    the naming convention then gives one to drop it by).
    """
    convention = {"fk": "%(table_name)s_%(column_0_name)s_fkey"}
    (name,) = (
        fk["name"] or f"{table}_{column}_fkey"
        for fk in sa.inspect(op.get_bind()).get_foreign_keys(table)
        if fk["constrained_columns"] == [column]
    )
    with op.batch_alter_table(table, naming_convention=convention) as batch:
        # MySQL and MariaDB drop a constraint by its kind: `type_` is required.
        batch.drop_constraint(name, type_="foreignkey")
        batch.drop_column(column)
