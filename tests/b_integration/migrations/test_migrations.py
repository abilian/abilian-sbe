# Copyright (c) 2012-2024, Abilian SAS

"""The latest migrations, down and up again, on SQLite.

The tables are made by `create_all`, as `flask initdb` makes them, then taken
down to an earlier revision and back: the migrations run on a schema like the
one a site has. SQLite is the database the tests run on; PostgreSQL and
MariaDB are run by hand (see each migration).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from flask_migrate import downgrade, stamp, upgrade

from abilian.sbe.apps.calendar.models import Event, EventAttachment
from abilian.services.viewtracker.models import Hit, View

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community

BEFORE_EVENT_FILES = "5b2e8c41d7a3"
BEFORE_EVENT_TYPES = "8d2e0f4a5b3c"
BEFORE_VIEW_INDEXES = "9e4f1a2b3c5d"


def at_revision(db: SQLAlchemy, revision: str) -> None:
    db.session.commit()
    stamp()
    downgrade(revision=revision)


def foreign_keys(db: SQLAlchemy, table: str) -> set[tuple[str, str]]:
    return {
        (fk["constrained_columns"][0], fk["referred_table"])
        for fk in sa.inspect(db.engine).get_foreign_keys(table)
    }


def test_an_event_s_files_and_thread_go_down_and_up(
    app: Application, db: SQLAlchemy
) -> None:
    at_revision(db, BEFORE_EVENT_FILES)
    assert ("thread_id", "forum_thread") not in foreign_keys(db, "sbe_event")
    assert ("_event_id", "sbe_event") not in foreign_keys(db, "cmisobject")

    upgrade()

    assert ("thread_id", "forum_thread") in foreign_keys(db, "sbe_event")
    assert ("_event_id", "sbe_event") in foreign_keys(db, "cmisobject")


def test_a_migrated_event_has_the_column_types_of_the_model(
    app: Application, db: SQLAlchemy, community1: Community
) -> None:
    if db.engine.dialect.name in ("mysql", "mariadb"):
        pytest.skip("No VARCHAR without a length: the tables never had other types")
    # An event with a file: SQLite copies the event table with rows referencing
    # it. Then, at the old types, a title longer than the model allows.
    event = Event(community=community1, title="Kick-off", start=datetime(2027, 1, 1))
    attachment = EventAttachment(name="agenda.txt")
    event.attachments.append(attachment)
    attachment.set_content(b"the agenda", "text/plain")
    db.session.add(event)
    at_revision(db, BEFORE_EVENT_TYPES)
    assert type_differences(db, "sbe_event")
    with db.engine.begin() as connection:
        connection.execute(sa.text("UPDATE sbe_event SET title = :t"), {"t": "x" * 300})

    upgrade()

    assert type_differences(db, "sbe_event") == []
    with db.engine.connect() as connection:
        title = connection.execute(sa.text("SELECT title FROM sbe_event")).scalar()
    assert title == "x" * 255


def type_differences(db: SQLAlchemy, table: str) -> list:
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diffs = compare_metadata(context, db.metadata)
    return [
        diff
        for group in diffs
        for diff in (group if isinstance(group, list) else [group])
        if diff[0] == "modify_type" and diff[2] == table
    ]


def test_duplicate_views_are_merged_with_their_hits(
    app: Application, db: SQLAlchemy, user: User
) -> None:
    at_revision(db, BEFORE_VIEW_INDEXES)
    # Views of entities since deleted: `entity_id` is kept, `_fk_entity_id` not.
    with db.engine.begin() as connection:
        connection.execute(
            sa.insert(View.__table__),
            [
                {"id": 1, "entity_id": 7, "user_id": user.id},
                {"id": 2, "entity_id": 7, "user_id": user.id},
                {"id": 3, "entity_id": 8, "user_id": user.id},
            ],
        )
        connection.execute(
            sa.insert(Hit.__table__), [{"view_id": 1}, {"view_id": 2}, {"view_id": 3}]
        )

    upgrade()

    with db.engine.connect() as connection:
        views = connection.execute(sa.select(View.id).order_by(View.id)).scalars()
        hits = connection.execute(sa.select(Hit.view_id).order_by(Hit.view_id))
        assert list(views) == [1, 3]
        assert list(hits.scalars()) == [1, 1, 3]
    indexes = {i["name"] for i in sa.inspect(db.engine).get_indexes("hit")}
    assert "ix_hit_view_id" in indexes
