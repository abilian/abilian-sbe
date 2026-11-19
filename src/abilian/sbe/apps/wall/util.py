# Copyright (c) 2012-2024, Abilian SAS

"""Some functions to retrieve activity entries."""

# TODO: move to the activity service ?
from __future__ import annotations

from typing import TYPE_CHECKING, cast

import sqlalchemy as sa
from flask import g
from werkzeug.exceptions import Forbidden

from abilian.core.extensions import db
from abilian.sbe.apps.communities.models import Membership
from abilian.sbe.apps.documents.models import Document, Folder
from abilian.services import get_service
from abilian.services.activity import ActivityEntry
from abilian.services.security import ADMIN, READ, SecurityService

if TYPE_CHECKING:
    from abilian.core.models.subjects import User
    from abilian.sbe.apps.communities.presenters import CommunityPresenter


def get_recent_entries(
    user: User,
    num: int = 20,
    actor: User | None = None,
    community: CommunityPresenter | None = None,
    kinds: tuple[type, ...] = (),
) -> list[ActivityEntry]:
    """What `user` may see of the latest activity, by `actor` or in `community`
    if given, on objects of one of `kinds` if any."""
    # Check just in case
    if not user.has_role(ADMIN):
        if community and not community.has_member(user):
            raise Forbidden

    query = ActivityEntry.query.options(sa.orm.joinedload(ActivityEntry.object))

    if community:
        query = query.filter(
            sa.or_(
                ActivityEntry.target == g.community,
                ActivityEntry.object == g.community,
            )
        )
    if actor:
        query = query.filter(ActivityEntry.actor == actor)
    if kinds:
        query = query.filter(
            ActivityEntry.object_type.in_([kind.entity_type for kind in kinds])
        )

    # Security check
    #
    # we use communities ids instead of object because as of sqlalchemy 0.8 the
    # 'in_' operator cannot be used with relationships, only foreign keys values
    if not community and not user.has_role(ADMIN):
        # `.values()` yields Row tuples, so unpack them: binding a Row into the
        # `in_()` below raises "type 'Row' is not supported".
        # Listed because we need them twice during query filtering.
        community_ids = [
            community_id
            for (community_id,) in Membership.query.filter(
                Membership.user_id == user.id
            ).values(Membership.community_id)
        ]
        if not community_ids:
            return []

        query = query.filter(
            sa.or_(
                ActivityEntry.target_id.in_(community_ids),
                ActivityEntry.object_id.in_(community_ids),
            )
        )

    query = query.order_by(ActivityEntry.happened_at.desc()).limit(1000)
    # get twice entries as needed, but ceil to 100
    limit = min(num * 2, 100)
    entries: list[ActivityEntry] = []
    deleted = False
    security = cast("SecurityService", get_service("security"))
    has_permission = security.has_permission

    for entry in query.yield_per(limit):
        if len(entries) >= num:
            break

        # Remove entries corresponding to deleted objects
        match entry.object:
            case None:
                db.session.delete(entry)
                deleted = True
                continue

            case Folder() | Document() if not has_permission(
                user, READ, obj=entry.object, inherit=True
            ):
                continue

        entries.append(entry)

    if deleted:
        db.session.commit()

    return entries
