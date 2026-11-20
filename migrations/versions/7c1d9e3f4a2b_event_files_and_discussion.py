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


def upgrade() -> None:
    op.add_column("sbe_event", sa.Column("thread_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "sbe_event_thread_id_fkey",
        "sbe_event",
        "forum_thread",
        ["thread_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("cmisobject", sa.Column("_event_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "cmisobject__event_id_fkey",
        "cmisobject",
        "sbe_event",
        ["_event_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("cmisobject__event_id_fkey", "cmisobject")
    op.drop_column("cmisobject", "_event_id")
    op.drop_constraint("sbe_event_thread_id_fkey", "sbe_event")
    op.drop_column("sbe_event", "thread_id")
