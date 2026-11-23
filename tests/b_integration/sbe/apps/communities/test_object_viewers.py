# Copyright (c) 2026, Abilian SAS

"""Who of the community has read a document, and when they last did."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import g

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.common import object_viewers
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.services.viewtracker import viewtracker
from tests.util import ensure_services_started

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def test_a_manager_sees_when_each_member_last_read_a_document(
    app: Application, db: SQLAlchemy, community1: Community
) -> None:
    """The last visit is a MAX() over the view's hits. Their relationship is
    ordered, and the query kept its ORDER BY: PostgreSQL refuses one in an
    aggregate. SQLite accepts it, so only a run on PostgreSQL would catch it
    coming back (`make test-postgres-docker`)."""
    ensure_services_started(["security"])
    manager = community1.test_user
    community1.set_membership(manager, MANAGER)
    reader = User(email="reader@example.com", can_login=True)
    db.session.add(reader)
    community1.set_membership(reader, MEMBER)
    document = community1.folder.create_document(title="minutes.txt")
    document.creator = manager
    db.session.commit()
    viewtracker.record_hit(entity=document, user=reader)
    viewtracker.record_hit(entity=document, user=reader)
    db.session.commit()
    hits = viewtracker.get_hits(views=viewtracker.get_views(entity=document))
    last_visit = max(hit.viewed_at for hit in hits)

    with app.test_request_context():
        g.community = community1
        viewers = object_viewers(manager, document)

    assert viewers == [{"user": reader, "viewed_at": last_visit}]
