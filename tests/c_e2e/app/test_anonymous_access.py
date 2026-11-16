# Copyright (c) 2012-2024, Abilian SAS

"""Every page refuses an anonymous visitor, except the ones listed public.

Each route used to carry its own protection, or not: anonymous visitors could
fetch any image stored in the database by its sequential id, upload files,
and reach the attachment, comment and tag views. This test makes a new route
refused by default: it fails until the route is protected, or listed here as
public on purpose.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import url_for

from abilian.core.models.subjects import Group

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community

#: Blueprints open to anyone: logging in, and the files every page needs.
PUBLIC_BLUEPRINTS = frozenset({"login"})

PUBLIC_ENDPOINTS = frozenset(
    {
        "static",
        "abilian_static",
        "abilian_sbe_static",
        "vite.static",
        # The landing page.
        "main.home",
        # The login form fetches its token.
        "csrf.json_token",
        # Followed from a notification email; the token says who.
        "notifications.unsubscribe_sbe",
    }
)

IGNORED_METHODS = frozenset({"HEAD", "OPTIONS"})


def _is_public(endpoint: str) -> bool:
    return (
        endpoint in PUBLIC_ENDPOINTS
        or endpoint.split(".", maxsplit=1)[0] in PUBLIC_BLUEPRINTS
    )


def test_every_private_route_refuses_an_anonymous_visitor(
    app: Application,
    client: FlaskClient,
    user: User,
    community: Community,
    db: SQLAlchemy,
) -> None:
    group = Group(name="A group")
    db.session.add(group)
    db.session.commit()
    # Real objects where a lookup happens before access control; any value
    # does for the others, since the visitor must be turned away first.
    values = {
        "community_id": community.slug,
        "user_id": user.id,
        "group_id": group.id,
        "stream_name": "all",
        # `forum/1` would be a thread's URL, not the forum's filtered list.
        "filter": "week",
    }

    not_refused = {}
    for rule in app.url_map.iter_rules():
        if _is_public(rule.endpoint):
            continue
        url = url_for(
            rule.endpoint, **{arg: values.get(arg, 1) for arg in rule.arguments}
        )
        for method in sorted(rule.methods - IGNORED_METHODS):
            response = client.open(url, method=method)
            sent_to_login = response.status_code == 302 and "/login" in (
                response.location or ""
            )
            if not (sent_to_login or response.status_code in {401, 403}):
                not_refused[f"{method} {url}"] = response.status_code

    assert not not_refused, f"answered an anonymous visitor: {not_refused}"
