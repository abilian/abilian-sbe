# Copyright (c) 2012-2024, Abilian SAS

"""Every route refuses a logged-in user who has no business there.

The anonymous sweep (`test_anonymous_access.py`) cannot see a route that asks
for a login and nothing more. This one logs in a user with no role and no
membership, and requests every route about objects that exist and belong to
others: a community they are not in, its documents and forum, another user's
profile, a private group. A route has to refuse them, or be listed below as
open to any logged-in user, with the reason.
"""

from __future__ import annotations

from secrets import token_hex
from typing import TYPE_CHECKING

from abilian.core.models.subjects import Group, User
from abilian.sbe.apps.forum.models import Post, Thread
from abilian.services import security_service
from tests.util import client_login

from .sweep import request_every_route
from .test_anonymous_access import _is_public

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community

OPEN_TO_ANY_USER = frozenset(
    {
        # The user's own communities, and their own home page and settings.
        "communities.index",
        "main.home",
        "social.home",
        "preferences.index",
        "preferences.user",
        "preferences.user_post",
        # Results are filtered by what the user may read.
        "search.live",
        "search.search_main",
        # The people directory, profiles and photos: an enterprise social
        # network shows its members to each other.
        "social.users",
        "social.users_json",
        "users.json_list",
        "social.user",
        "users.photo",
        "images.user_photo",
        "images.user_default",
        "communities.community_default_image",
        # Following someone, and posting to the user's own stream.
        "social.user_post",
        "social.share",
        # The user's own uploads: a handle is looked up in their directory.
        "uploads.new_file",
        "uploads.handle",
    }
)

#: Asked of an entity that no model registers as commentable or attachable:
#: refused as a bad request before any permission is asked, which their own
#: tests cover (`tests/b_integration/web/{comments,attachments}`).
NOT_REACHABLE = frozenset({"attachments", "comments"})

#: Logging out would end the sweep's session.
LOGOUT = frozenset({"login.logout", "login.logout_json"})


def _skipped(endpoint: str) -> bool:
    return (
        _is_public(endpoint)
        or endpoint in OPEN_TO_ANY_USER
        or endpoint in LOGOUT
        or endpoint.split(".", maxsplit=1)[0] in NOT_REACHABLE
    )


def test_every_route_refuses_a_user_with_no_business_there(
    app: Application, client: FlaskClient, db: SQLAlchemy, community1: Community
) -> None:
    security_service.start()
    outsider = User(email="outsider@example.com", password=token_hex(), can_login=True)
    group = Group(name="A private group")
    document = community1.folder.create_document("secret.txt")
    document.set_content(b"secret", "text/plain")
    thread = Thread(title="A thread", community=community1)
    post = Post(thread=thread, body_html="hello")
    db.session.add_all([outsider, group, thread, post])
    db.session.commit()
    values = {
        "community_id": community1.slug,
        "user_id": community1.test_user.id,
        "group_id": group.id,
        "doc_id": document.id,
        "folder_id": community1.folder.id,
        "entity_id": document.id,
        "object_id": document.id,
        "thread_id": thread.id,
        "post_id": post.id,
        # `forum/1` would be a thread's URL, not the forum's filtered list.
        "filter": "week",
    }

    not_refused = {}
    with client_login(client, outsider):
        for request, response in request_every_route(app, client, values, _skipped):
            if response.status_code not in {403, 404}:
                not_refused[request] = response.status_code

    assert not not_refused, f"answered an outsider: {not_refused}"
