# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import pkgutil

import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm
from flask import Response, flash, jsonify, redirect, render_template, request
from flask_login import current_user
from loguru import logger
from sqlalchemy.sql.expression import and_, func, or_
from werkzeug.exceptions import BadRequest

from abilian.core.extensions import db
from abilian.core.models.subjects import User
from abilian.i18n import _, _l
from abilian.sbe.apps.communities.models import Membership
from abilian.sbe.apps.social.forms import UserProfileForm, UserProfileViewForm
from abilian.sbe.apps.wall.presenters import ActivityEntryPresenter
from abilian.sbe.apps.wall.views import get_recent_entries
from abilian.services import security_service
from abilian.services.security import is_site_admin
from abilian.web import url_for
from abilian.web.listing import Listing
from abilian.web.views import ObjectEdit, default_view

from .social import social

DEFAULT_USER_MUGSHOT = pkgutil.get_data(
    "abilian.sbe", "static/images/silhouette_unknown.png"
)


def make_tabs(user: User) -> list[dict[str, str]]:
    return [
        {"id": "profile", "label": _("Profile"), "link": url_for(user, tab="profile")},
        # dict(id='conversations', label=_(u'Conversations'), link=url_for(user), is_online=True),
        {
            "id": "documents",
            "label": _("Documents"),
            "link": url_for(user, tab="documents"),
        },
        {"id": "images", "label": _("Images"), "link": url_for(user, tab="images")},
        {"id": "audit", "label": _("Audit"), "link": url_for(user, tab="audit")},
    ]


_NAME = (func.lower(User.last_name), func.lower(User.first_name))
DIRECTORY_SORT_COLUMNS = {
    "name": _NAME,
    "created_at": (User.created_at, *_NAME),
    "last_active": (User.last_active, *_NAME),
}


@social.route("/users/")
def users() -> str:
    listing, users = Listing.from_query(
        User.query, DIRECTORY_SORT_COLUMNS, "name", (User.first_name, User.last_name)
    )
    return render_template("social/users.html", listing=listing, users=users)


@social.route("/users/<int:user_id>")
@default_view(social, User, "user_id")
def user(user_id: int) -> str:
    user = User.query.get(user_id)

    # FIXME: use user profiles
    view_form = UserProfileViewForm(obj=user)

    communities = [m.community for m in user.communautes_membership]
    if current_user != user and (
        not security_service.has_role(current_user, "manager")
    ):
        # filter visible communautes (ticket 165)
        communities = [c for c in communities if c.has_member(current_user)]

    view_form.communautes._set_data(communities)

    # FIXME
    contact = user
    entries = get_recent_entries(user=user)
    entries = ActivityEntryPresenter.wrap_collection(entries)
    ctx = {
        "user": user,
        "contact": contact,
        "view_form": view_form,
        "can_edit": can_edit(user),
        "tabs": make_tabs(user),
        "activity_entries": entries,
    }
    return render_template("social/user.html", **ctx)


def can_edit(user: User) -> bool:
    # TODO: introduce a "self" role?
    return (user == current_user) or is_site_admin()


class UserProfileEdit(ObjectEdit):
    Model = User
    Form = UserProfileForm
    pk = "user_id"
    _message_success = _l("Profile edited")

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)
        self.user = self.obj
        return args, kwargs

    def view_url(self):
        return url_for(".user", user_id=self.user.id)

    def edit(self):
        if not can_edit(self.user):
            return Response(status=403)
        return super().edit()

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
def user_post(user_id):
    user = User.query.get(user_id)
    action = request.form.get("action")
    return_url = request.form.get("return_url")

    match action:
        case "follow":
            current_user.follow(user)
        case "unfollow":
            current_user.unfollow(user)
        case _:
            msg = "Should not happen"
            raise Exception(msg)
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
            .options(sa.orm.noload("user"), sa.orm.noload("community"))
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
