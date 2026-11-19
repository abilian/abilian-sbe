# Copyright (c) 2012-2026, Abilian SAS

"""Mon fil: the news of a user's communities, as entries a page can lay out.

An `ActivityEntry` says who did what to which object, and where. `feed_item()` turns one
into what an entry of the feed shows: a sentence ("Paul Girard a lancé une discussion"),
the community and the section it happened in, a title, a few lines of text, files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import bleach
from markupsafe import Markup

from abilian.i18n import _l
from abilian.sbe.apps.calendar.models import Event
from abilian.sbe.apps.communities.models import Community
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.forum.models import Post, Thread
from abilian.sbe.apps.wiki.models import WikiPage
from abilian.web.util import url_for

if TYPE_CHECKING:
    from datetime import datetime

    from abilian.core.models.subjects import User
    from abilian.services.activity.models import ActivityEntry

#: What the actor did, by verb and kind of object; the actor's name comes first.
#: Lazy: evaluated in the language of the request that shows them.
ACTIONS: dict[tuple[str, type], str] = {
    ("post", Thread): _l("started a discussion"),
    ("post", Post): _l("replied to a discussion"),
    ("post", Document): _l("posted a document"),
    ("update", Document): _l("updated a document"),
    ("post", WikiPage): _l("created a wiki page"),
    ("update", WikiPage): _l("updated a wiki page"),
    ("post", Event): _l("added an event"),
    ("post", Community): _l("created the community"),
    ("update", Community): _l("updated the community"),
    ("join", Community): _l("joined the community"),
    ("leave", Community): _l("left the community"),
}

#: The community's section each kind of object belongs to.
SECTIONS: dict[type, str] = {
    Thread: _l("Discussions"),
    Post: _l("Discussions"),
    Document: _l("Documents"),
    WikiPage: _l("Wiki"),
    Event: _l("Calendar"),
    Community: _l("Members"),
}

#: Mon fil's filters: the name in the address, the kinds of object kept. Each is
#: labelled with its kinds' section.
FILTERS: dict[str, tuple[type, ...]] = {
    "discussions": (Thread, Post),
    "documents": (Document,),
    "calendar": (Event,),
    "wiki": (WikiPage,),
}

#: How much of a post an entry shows; the page cuts it further, to three lines.
EXCERPT_LENGTH = 300


@dataclass(frozen=True)
class FeedFile:
    name: str | None
    url: str
    size: int


@dataclass(frozen=True)
class FeedItem:
    actor: User
    action: str
    happened_at: datetime
    community: Community | None
    section: str
    title: str
    url: str
    excerpt: str
    files: tuple[FeedFile, ...]


def feed_item(entry: ActivityEntry) -> FeedItem:
    """What an entry of the feed shows for one activity."""
    obj = entry.object
    kind = type(obj)
    action = ACTIONS.get((entry.verb or "", kind), _l("posted something"))
    community = entry.target if isinstance(entry.target, Community) else None
    if isinstance(obj, Community):
        community = obj
    title, text, files = _content(obj)
    # Set on insert by the column's default; the model types it as nullable.
    assert entry.happened_at is not None
    return FeedItem(
        actor=entry.actor,
        action=str(action),
        happened_at=entry.happened_at,
        community=community,
        section=str(SECTIONS.get(kind, "")),
        title=title,
        url=url_for(obj),
        excerpt=text,
        files=files,
    )


def _content(obj: object) -> tuple[str, str, tuple[FeedFile, ...]]:
    """An object's title, text and files, as an entry shows them."""
    match obj:
        case Thread():
            first = obj.posts[0]
            return obj.title, excerpt(first.body_html, EXCERPT_LENGTH), _files(first)
        case Post():
            return obj.thread.title, excerpt(obj.body_html, EXCERPT_LENGTH), _files(obj)
        case Document():
            return "", "", (FeedFile(obj.name, url_for(obj), obj.content_length),)
        case Community():
            return "", "", ()
        case _:
            return getattr(obj, "title", "") or getattr(obj, "name", ""), "", ()


def excerpt(html: str, limit: int = 400) -> str:
    """The text of user-written HTML, without its markup, cut at `limit` characters."""
    text = Markup(bleach.clean(html, tags=set(), strip=True)).unescape()
    return f"{text[:limit]}…" if len(text) > limit else text


def _files(post: Post) -> tuple[FeedFile, ...]:
    return tuple(
        FeedFile(a.name, url_for(a), a.content_length) for a in post.attachments
    )
