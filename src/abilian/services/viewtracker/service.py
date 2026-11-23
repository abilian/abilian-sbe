# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from abilian.core.extensions import db
from abilian.services import Service

from .models import Hit, View

if TYPE_CHECKING:
    from abilian.core.entities import Entity
    from abilian.core.models.subjects import User

__all__ = ["viewtracker"]


class ViewTracker(Service):
    name = "viewtracker"

    @staticmethod
    def record_hit(entity: Entity, user: User) -> None:
        """Record that `user` viewed `entity`; the caller commits."""
        # Ids, not the objects: the user may be a thread-local proxy.
        views = View.query.filter(View.entity_id == entity.id, View.user_id == user.id)
        view = views.one_or_none()
        if view is None:
            try:
                with db.session.begin_nested():
                    view = View(entity=entity, user_id=user.id)
                    db.session.add(view)
            except IntegrityError:
                # Another request added it since: one view per (entity, user).
                view = views.one()
        db.session.add(Hit(view=view))
        db.session.flush()

    @staticmethod
    def get_views(entity=None, entities=None, user=None, users=None):
        assert entity is None or entities is None
        assert entity is not None or entities is not None
        assert user is None or users is None

        if entities is None:
            entities = []
        if entity:
            entities += [entity]

        if users is None:
            users = []
        if user is not None:
            users += [user]

        query = View.query
        if entities:
            entity_ids = [entity_.id for entity_ in entities]
            query = query.filter(View.entity_id.in_(entity_ids))

        if users:
            user_ids = [user_.id for user_ in users]
            query = query.filter(View.user_id.in_(user_ids))

        return query.all()

    @staticmethod
    def get_hits(views=None, view=None):
        assert view is not None or views is not None

        if views is None:
            views = []
        if view is not None:
            views += [view]

        view_ids = [view_.id for view_ in views]
        return (
            Hit.query.filter(Hit.view_id.in_(view_ids))
            .order_by(Hit.viewed_at.asc())
            .all()
        )


viewtracker = ViewTracker()
