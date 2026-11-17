# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from email.feedparser import FeedParser
from typing import TYPE_CHECKING

from abilian.sbe.apps.forum.models import Thread
from tests.util import DATA_DIR

if TYPE_CHECKING:
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def started_thread(
    db: SQLAlchemy, community: Community, author: User, title: str, replies: int = 0
) -> Thread:
    """A thread `author` started in `community`, with `replies` replies of theirs."""
    thread = Thread(title=title, community=community)
    thread.creator = thread.owner = author
    for body in ["<p>Hello.</p>"] + ["<p>Agreed.</p>"] * replies:
        post = thread.create_post(body_html=body)
        post.creator = post.owner = author
    db.session.add(thread)
    db.session.commit()
    return thread


def get_string_from_file(filename="notification.email"):
    """Load a test email, return as string."""
    filepath = DATA_DIR / "forum" / filename
    with filepath.open("rt", encoding="utf-8") as email_file:
        email_string = email_file.read()
    return email_string


def get_email_message_from_file(filename="notification.email"):
    """Load a mail and parse it into a email.message."""
    email_string = get_string_from_file(filename)
    parser = FeedParser()
    parser.feed(email_string)
    email_message = parser.close()
    return email_message
