# Copyright (c) 2012-2026, Abilian SAS

"""Main views."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from flask import Blueprint, redirect, render_template, request, url_for
from werkzeug.exceptions import NotFound

from abilian.core.extensions import db
from abilian.core.extensions.login import authenticated
from abilian.sbe.apps.calendar.models import Event
from abilian.sbe.apps.communities.models import communities_of
from abilian.sbe.apps.wall.util import get_recent_entries
from abilian.services import get_service
from abilian.services.activity import ActivityEntry

from .feed import FILTERS, SECTIONS, feed_item

if TYPE_CHECKING:
    from werkzeug.wrappers import Response

    from abilian.core.models.subjects import User
    from abilian.sbe.apps.communities.models import Community

__all__ = ("blueprint",)

blueprint = Blueprint("main", __name__, url_prefix="")
route = blueprint.route

#: How many entries Mon fil shows.
FEED_LENGTH = 30

#: How many communities the column beside the feed lists, the most active first.
COMMUNITIES_SHOWN = 8

#: How many events to come the column beside the feed lists, soonest first.
EVENTS_SHOWN = 3

#: The preference that keeps when the user last marked Mon fil read, in UTC as the
#: activity's dates are: what came after is new.
READ_UNTIL_KEY = "feed:read_until"


@route("/")
@authenticated
def home(user: User) -> str:
    """Mon fil: the news of the user's communities, newest first, of one kind if
    `?kind=` names a filter; beside it, the communities and the events to come."""
    kind = request.args.get("kind")
    if kind is not None and kind not in FILTERS:
        raise NotFound
    communities = communities_of(user)
    entries = get_recent_entries(user, FEED_LENGTH, kinds=FILTERS.get(kind, ()))
    items = [feed_item(entry) for entry in entries]
    seen = read_until(user)
    return render_template(
        "main/home.html",
        items=items,
        read_until=seen,
        new_count=sum(item.happened_at > seen for item in items),
        filters={name: SECTIONS[kinds[0]] for name, kinds in FILTERS.items()},
        kind=kind,
        communities=communities[:COMMUNITIES_SHOWN],
        communities_count=len(communities),
        new_in=new_by_community(communities[:COMMUNITIES_SHOWN], seen),
        coming=events_to_come(communities),
    )


def new_by_community(communities: list[Community], since: datetime) -> dict[int, int]:
    """How many entries came in each of `communities` after `since`, by its id."""
    # ponytail: counts what the feed would leave out too (a document in a folder one
    # may not open); filter as `get_recent_entries` does if the counts mislead.
    rows = db.session.execute(
        sa.select(ActivityEntry.target_id, sa.func.count())
        .where(
            ActivityEntry.target_id.in_([c.id for c in communities]),
            ActivityEntry.happened_at > since,
        )
        .group_by(ActivityEntry.target_id)
    )
    return dict(rows.tuples().all())


def news_in(user: User, communities: list[Community]) -> dict[int, int]:
    """What is new in each of `communities` since `user` last marked Mon fil read,
    by its id, for the bar; nothing before their first visit to Mon fil. With no
    community (an anonymous visitor's case), nothing is asked."""
    if not communities:
        return {}
    stored = get_service("preferences").get_preferences(user).get(READ_UNTIL_KEY)
    if stored is None:
        return {}
    return new_by_community(communities, datetime.fromisoformat(stored))


def events_to_come(communities: list[Community]) -> list[Event]:
    """The next events of `communities`, soonest first."""
    return (
        Event.query.filter(
            Event.community_id.in_([c.id for c in communities]),
            Event.end > datetime.now(),
        )
        .order_by(Event.start)
        .limit(EVENTS_SHOWN)
        .all()
    )


@route("/read", methods=["POST"])
@authenticated
def feed_read(user: User) -> Response:
    """Mon fil marked read: nothing that came so far is new any more."""
    mark_read(user)
    kind = request.form.get("kind")
    return redirect(url_for(".home", kind=kind if kind in FILTERS else None))


def read_until(user: User) -> datetime:
    """When `user` last marked Mon fil read; on their first visit, now."""
    preferences = get_service("preferences").get_preferences(user)
    stored = preferences.get(READ_UNTIL_KEY)
    return mark_read(user) if stored is None else datetime.fromisoformat(stored)


def mark_read(user: User) -> datetime:
    """Now, kept as when `user` last marked Mon fil read."""
    now = datetime.utcnow()
    get_service("preferences").set_preferences(
        user, **{READ_UNTIL_KEY: now.isoformat()}
    )
    db.session.commit()
    return now
