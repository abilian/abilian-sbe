# Copyright (c) 2012-2026, Abilian SAS

"""What a person opened lately: the discussions, wiki pages and documents whose
views the view tracker records, those they may still read, latest first."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from abilian.core.extensions import db
from abilian.sbe.apps.communities.security import is_member
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.documents.repository import content_repository
from abilian.services.viewtracker.models import Hit, View

if TYPE_CHECKING:
    from abilian.core.entities import Entity
    from abilian.core.models.subjects import User

#: How many the bar's search shows on an empty field.
RECENTLY_OPENED = 3

#: How many views are read to find them: some are of what one may no longer read.
LOOKED_AT = 4 * RECENTLY_OPENED


def recently_opened(user: User) -> list[Entity]:
    """What `user` opened lately and may still read, latest first."""
    last_hit = sa.func.max(Hit.viewed_at)
    views = db.session.scalars(
        sa.select(View)
        .join(Hit, Hit.view_id == View.id)
        .where(View.user_id == user.id, View._fk_entity_id.is_not(None))
        .group_by(View.id)
        .order_by(last_hit.desc())
        .limit(LOOKED_AT)
    )
    readable = [view.entity for view in views if may_read(user, view.entity)]
    return readable[:RECENTLY_OPENED]


def may_read(user: User, entity: Entity) -> bool:
    """`entity` is in one of `user`'s communities, and a document is open to them
    there. The rights are asked again: one leaves a community, a folder closes."""
    community = getattr(entity, "community", None)
    if community is None or not is_member(user, community):
        return False
    return not isinstance(entity, Document) or content_repository.has_access(
        user, entity
    )
