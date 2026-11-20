# Copyright (c) 2026, Abilian SAS

"""The communities to discover: those their managers opened, which one is not in.
Each shows what it is for, its managers, its size and when it last moved, never
what it holds; one joins it at once, or asks to, as its managers chose. Outside
any community's address, which only its members reach."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import current_app, flash, redirect, render_template, request
from werkzeug.exceptions import BadRequest

from abilian.core.extensions import db
from abilian.core.extensions.login import authenticated
from abilian.core.signals import activity
from abilian.core.util import unwrap
from abilian.i18n import _
from abilian.sbe.apps.communities.invitations import send_join_request
from abilian.sbe.apps.communities.models import (
    MEMBER,
    ON_REQUEST,
    OPEN,
    Community,
    MembershipRequest,
    communities_to_discover,
    managers_of,
)
from abilian.web import csrf, url_for

from .views import route

if TYPE_CHECKING:
    from werkzeug.wrappers import Response

    from abilian.core.models.subjects import User


@route("/discover/")
@authenticated
def discover(user: User) -> str:
    communities = communities_to_discover(user)
    asked = {
        asking.community_id
        for asking in MembershipRequest.query.filter(
            MembershipRequest.user_id == user.id
        )
    }
    return render_template(
        "community/discover.html",
        communities=communities,
        managers=managers_of(communities),
        asked=asked,
        ON_REQUEST=ON_REQUEST,
    )


@route("/discover/", methods=["POST"])
@csrf.protect
@authenticated
def discover_post(user: User) -> Response:
    """Join an open community, or ask to join one open on request."""
    community = _community_to_join(user, request.form.get("community", ""))
    match (request.form.get("action"), community.visibility):
        case ("join", visibility) if visibility == OPEN:
            community.set_membership(user, MEMBER)
            activity.send(
                unwrap(current_app), actor=user, verb="join", object=community
            )
            db.session.commit()
            flash(_("Welcome to %(name)s.", name=community.name), "success")
            return redirect(url_for(community))
        case ("ask", visibility) if visibility == ON_REQUEST:
            if not MembershipRequest.query.filter_by(
                community_id=community.id, user_id=user.id
            ).count():
                asking = MembershipRequest(community=community, user=user)
                db.session.add(asking)
                db.session.commit()
                send_join_request(asking)
            flash(
                _(
                    "Your request to join %(name)s went to its managers.",
                    name=community.name,
                ),
                "success",
            )
            return redirect(url_for(".discover"))
    msg = "Not a way into this community"
    raise BadRequest(msg)


def _community_to_join(user: User, slug: str) -> Community:
    """The community a form names, which `user` may find here: open, and not theirs."""
    community = next((c for c in communities_to_discover(user) if c.slug == slug), None)
    if community is None:
        msg = "Not a community to discover"
        raise BadRequest(msg)
    return community
