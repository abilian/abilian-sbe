# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import pkgutil
from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm
from flask import flash, jsonify, redirect, render_template, request
from loguru import logger
from sqlalchemy.sql.expression import and_, func, or_
from werkzeug.exceptions import BadRequest, Forbidden

from abilian.core.extensions import db
from abilian.core.extensions.login import authenticated, authenticated_user
from abilian.core.models.subjects import User
from abilian.i18n import _, _l
from abilian.sbe.apps.communities.models import Membership
from abilian.sbe.apps.main.feed import feed_item
from abilian.sbe.apps.social.forms import UserProfileForm
from abilian.sbe.apps.wall.views import get_recent_entries
from abilian.services import security_service
from abilian.services.security import is_site_admin
from abilian.web import url_for
from abilian.web.listing import Listing
from abilian.web.views import ObjectEdit, default_view

from .social import social

if TYPE_CHECKING:
    from werkzeug.wrappers import Response

DEFAULT_USER_MUGSHOT = pkgutil.get_data(
    "abilian.sbe", "static/images/silhouette_unknown.png"
)


_NAME = (func.lower(User.last_name), func.lower(User.first_name))
DIRECTORY_SORT_COLUMNS = {
    "name": _NAME,
    "created_at": (User.created_at, *_NAME),
    "last_active": (User.last_active, *_NAME),
}


@social.route("/users/")
@authenticated
def users(user: User) -> str:
    """The directory: the people I share a community with, or everyone.

    Mine first, when I am in a community; the communities each one shares with me.
    """
    mine = [
        community_id
        for (community_id,) in Membership.query.filter(
            Membership.user_id == user.id
        ).values(Membership.community_id)
    ]
    neighbours = User.query.filter(
        User.id.in_(
            db.session.query(Membership.user_id).filter(
                Membership.community_id.in_(mine)
            )
        )
    )
    everyone = request.args.get("who") == "all" or not mine
    listing, people = Listing.from_query(
        User.query if everyone else neighbours,
        DIRECTORY_SORT_COLUMNS,
        "name",
        (User.first_name, User.last_name),
    )
    return render_template(
        "social/users.html",
        listing=listing,
        users=people,
        everyone=everyone,
        counts={"mine": neighbours.count() if mine else 0, "all": User.query.count()},
        shared=communities_in_common(people, mine),
    )


def communities_in_common(people: list[User], mine: list[int]) -> dict[int, list]:
    """For each person, by id, the communities they are in that I am in too."""
    shared: dict[int, list] = {person.id: [] for person in people}
    memberships = Membership.query.filter(
        Membership.user_id.in_(shared), Membership.community_id.in_(mine)
    )
    for membership in memberships:
        shared[membership.user_id].append(membership.community)
    return shared


@social.route("/users/<int:user_id>")
@default_view(social, User, "user_id")
@authenticated
def user(user: User, user_id: int) -> str:
    """A person: how to reach them, what they did lately where `user` can see it,
    and their communities."""
    shown = User.query.get_or_404(user_id)
    communities = [m.community for m in shown.communautes_membership]
    in_common = user != shown and not security_service.has_role(user, "manager")
    if in_common:
        # Only those the viewer is in too (ticket 165).
        communities = [c for c in communities if c.has_member(user)]

    return render_template(
        "social/user.html",
        person=shown,
        communities=communities,
        in_common=in_common,
        may_edit=can_edit(user, shown),
        items=[feed_item(entry) for entry in get_recent_entries(user, actor=shown)],
    )


def can_edit(user: User, profile_owner: User) -> bool:
    """May `user` edit the profile of `profile_owner`?"""
    # TODO: introduce a "self" role?
    return user == profile_owner or is_site_admin(user)


class UserProfileEdit(ObjectEdit[User, UserProfileForm]):
    Model = User
    Form = UserProfileForm
    pk = "user_id"
    _message_success = _l("Profile edited")

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)
        self.user = self.obj
        # Checked here, not on submit only: the form shows the profile too.
        if not can_edit(authenticated_user(), self.user):
            raise Forbidden
        return args, kwargs

    def view_url(self):
        return url_for(".user", user_id=self.user.id)

    def handle_commit_exception(self, exc):
        db.session.rollback()
        if isinstance(exc, sa.exc.IntegrityError):
            log_msg = "Error saving user profile"
        else:
            log_msg = "Unexpected error while saving user profile"
        logger.opt(exception=True).error(log_msg, extra={"stack": True})
        flash(_("Error occured"), "error")
        return self.redirect_to_view()


social.route("/users/<int:user_id>/edit")(UserProfileEdit.as_view("user_edit"))


@social.route("/users/<int:user_id>", methods=["POST"])
@authenticated
def user_post(user: User, user_id: int) -> Response:
    followed = User.query.get_or_404(user_id)
    action = request.form.get("action")
    return_url = request.form.get("return_url")

    match action:
        case "follow":
            user.follow(followed)
        case "unfollow":
            user.unfollow(followed)
        case _:
            msg = f"Unknown action: {action}"
            raise BadRequest(msg)
    db.session.commit()

    if return_url:
        # TODO: security check
        return redirect(return_url)
    return redirect(url_for(".user_view", user_id=user_id))


#
# Ad-hoc JSON endpoints, used by select boxes
#
@social.route("/users/json")
def users_json():
    q = request.args.get("q", "").replace("%", " ").strip().lower()
    if len(q) < 2:
        raise BadRequest

    query = User.query.filter(
        or_(
            func.lower(User.first_name).like(f"{q}%"),
            func.lower(User.last_name).like(f"{q}%"),
        )
    ).order_by(func.lower(User.last_name))

    with_membership = request.args.get("with_membership")
    if with_membership is not None:
        # provide membership info for a community
        with_membership = int(with_membership)
        query = (
            query.outerjoin(
                Membership,
                and_(
                    Membership.user.expression,
                    Membership.community_id == with_membership,
                ),
            )
            .filter(User.can_login == True)
            .add_columns(Membership.role)
        )

    exclude_community = request.args.get("exclude_community")
    if exclude_community is not None:
        exclude_community = int(exclude_community)
        exclude = (
            ~Membership.query.filter(
                Membership.user.expression, Membership.community_id == exclude_community
            )
            .options(
                sa.orm.noload(Membership.user), sa.orm.noload(Membership.community)
            )
            .exists()
        )
        query = query.filter(exclude)

    results = []
    for user in query.all():
        role = None
        if with_membership is not None:
            user, role = user

        if role is not None:
            role = str(role)

        item = {
            "id": user.id,
            "text": f"{user.name} ({user.email})",
            "name": user.name,
            "email": user.email,
            "role": role,
        }
        results.append(item)

    return jsonify({"results": results})
