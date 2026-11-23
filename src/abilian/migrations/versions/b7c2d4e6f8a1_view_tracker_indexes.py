"""One view per user and entity, and the indexes the view tracker reads by.

Two requests could each find no view of an entity by a user and both create
one; a unique index stops that. Existing duplicates are merged first:
their hits go to the oldest view, the others are deleted.

Revision ID: b7c2d4e6f8a1
Revises: 9e4f1a2b3c5d
Create Date: 2026-11-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7c2d4e6f8a1"
down_revision = "9e4f1a2b3c5d"
branch_labels = None
depends_on = None


# Indexes, not constraints: every database, SQLite included, adds and drops
# them without recreating the table.
def upgrade() -> None:
    merge_duplicate_views()
    op.create_index(
        "uq_view_entity_id_user_id", "view", ["entity_id", "user_id"], unique=True
    )
    if not indexes_foreign_keys():
        op.create_index("ix_view_user_id", "view", ["user_id"])
        op.create_index("ix_hit_view_id", "hit", ["view_id"])


def downgrade() -> None:
    if not indexes_foreign_keys():
        op.drop_index("ix_hit_view_id", table_name="hit")
        op.drop_index("ix_view_user_id", table_name="view")
    op.drop_index("uq_view_entity_id_user_id", table_name="view")


def indexes_foreign_keys() -> bool:
    """True on MySQL and MariaDB, which index every foreign key column.

    There `view.user_id` and `hit.view_id` are indexed already, and the index
    a foreign key uses cannot be dropped.
    """
    return op.get_bind().dialect.name in ("mysql", "mariadb")


def merge_duplicate_views() -> None:
    """Keep the oldest view of each (entity, user), with the hits of the others.

    One group at a time, with no subquery on the table a statement changes:
    MySQL and MariaDB refuse those, and duplicates are few.
    """
    view = sa.table(
        "view", sa.column("id"), sa.column("entity_id"), sa.column("user_id")
    )
    hit = sa.table("hit", sa.column("view_id"))
    connection = op.get_bind()
    groups = connection.execute(
        sa.select(view.c.entity_id, view.c.user_id, sa.func.min(view.c.id))
        .group_by(view.c.entity_id, view.c.user_id)
        .having(sa.func.count() > 1)
    ).all()
    for entity_id, user_id, keeper_id in groups:
        duplicate = sa.and_(
            view.c.entity_id == entity_id,
            view.c.user_id == user_id,
            view.c.id != keeper_id,
        )
        duplicate_ids = sa.select(view.c.id).where(duplicate)
        connection.execute(
            hit.update()
            .where(hit.c.view_id.in_(duplicate_ids))
            .values(view_id=keeper_id)
        )
        connection.execute(view.delete().where(duplicate))
