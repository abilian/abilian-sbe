# Copyright (c) 2012-2026, Abilian SAS

"""Main views."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from flask import Blueprint, render_template, request
from werkzeug.exceptions import NotFound

from abilian.core.extensions.login import authenticated
from abilian.sbe.apps.calendar.models import Event
from abilian.sbe.apps.communities.models import communities_of
from abilian.sbe.apps.wall.util import get_recent_entries

from .feed import FILTERS, SECTIONS, feed_item

if TYPE_CHECKING:
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
    return render_template(
        "main/home.html",
        items=[feed_item(entry) for entry in entries],
        filters={name: SECTIONS[kinds[0]] for name, kinds in FILTERS.items()},
        kind=kind,
        communities=communities[:COMMUNITIES_SHOWN],
        communities_count=len(communities),
        coming=events_to_come(communities),
    )


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
