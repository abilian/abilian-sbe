# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flask import (
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_babel import gettext as _
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from abilian.core.extensions import db
from abilian.core.extensions.login import authenticated
from abilian.core.models.subjects import Group, User
from abilian.services.image import CROP, resize
from abilian.services.security import is_site_admin
from abilian.web import csrf
from abilian.web.views import default_view

from .social import social

if TYPE_CHECKING:
    from werkzeug.wrappers import Response

DEFAULT_GROUP_MUGSHOT = (
    Path(__file__).parent / ".." / ".." / ".." / "static" / "images" / "frog.jpg"
).read_bytes()


@social.route("/groups/")
@authenticated
def groups(user: User) -> str:
    tab = request.args.get("tab", "all_groups")
    if tab == "all_groups":
        groups = [
            group
            for group in Group.query.order_by(Group.name).all()
            if can_see(user, group)
        ]
    else:
        groups = sorted(user.groups, key=lambda group: group.name)

    return render_template("social/groups.html", groups=groups)


def is_admin(user: User, group: Group) -> bool:
    """May `user` administer `group`?

    Group administrators are a relationship on `Group`, not role assignments,
    so this cannot be `has_role(user, ADMIN, group)` yet.
    """
    if user in group.admins:
        return True
    return "security" in current_app.extensions and is_site_admin(user)


def can_see(user: User, group: Group) -> bool:
    """May `user` see `group`? Anyone a public one; a private one, only its
    members and administrators."""
    return group.public or user in group.members or is_admin(user, group)


def get_visible_group(user: User, group_id: int) -> Group:
    """The group, or a 404 if `user` may not see it: the group list does not
    show it to them either."""
    group = Group.query.get_or_404(group_id)
    if not can_see(user, group):
        raise NotFound
    return group


@social.route("/groups/<int:group_id>")
@default_view(social, Group, "group_id")
@authenticated
def group_home(user: User, group_id: int) -> str:
    group = get_visible_group(user, group_id)
    ctx = {"group": group, "is_admin": is_admin(user, group)}
    return render_template("social/group.html", **ctx)


@social.route("/groups/<int:group_id>/json")
@authenticated
def group_json(user: User, group_id: int) -> Response:
    members = get_visible_group(user, group_id).members
    q = request.args.get("q", "").lower()
    if q:
        members = [
            u
            for u in members
            if any(
                term.startswith(q)
                for name in (u.first_name.lower(), u.last_name.lower())
                for term in name.split()
            )
        ]

    result = {"results": [{"id": obj.id, "text": obj.name} for obj in members]}
    return jsonify(result)


@social.route("/groups/<int:group_id>", methods=["POST"])
@csrf.protect
@authenticated
def group_post(user: User, group_id: int) -> Response:
    group = get_visible_group(user, group_id)
    action = request.form.get("action")
    return_url = request.form.get("return_url")
    user_id = request.form.get("user", "").strip()

    membership_actions = frozenset(("add", "remove", "add-admin", "remove-admin"))

    if action not in {"join", "leave"} | membership_actions:
        msg = f"Unknown action: {action}"
        raise BadRequest(msg)

    # Members of a private group are added by its administrators.
    if action == "join" and not group.public:
        raise Forbidden

    # Everything but join and leave writes somebody else's membership, and
    # add-admin writes who may do that. This was an `assert`, which `python -O`
    # compiles out entirely and which raises a 500 rather than refusing when it
    # is compiled in.
    if action not in ("join", "leave") and not is_admin(user, group):
        raise Forbidden

    if action == "join":
        user.join(group)
    elif action == "leave":
        user.leave(group)

    elif action in membership_actions:
        try:
            user_id = int(user_id)
        except ValueError:
            flash(_("Error: No user selected"), "error")
            return redirect(url_for(".group_home", group_id=group_id))

        member = User.query.get_or_404(user_id)

        match action:
            case "add":
                member.join(group)
            case "remove":
                member.leave(group)
            case "add-admin":
                if member not in group.admins:
                    group.admins.add(member)
            case "remove-admin":
                if member in group.admins:
                    group.admins.remove(member)

    db.session.commit()

    if not return_url:
        return_url = url_for(".group_home", group_id=group_id)

    # TODO: security check
    return redirect(return_url)


@social.route("/groups/<int:group_id>/mugshot")
@authenticated
def group_mugshot(user: User, group_id: int) -> Response:
    # TODO: duplicated code (with user_mugshot). Extract common method.
    size = request.args.get("s", 55, type=int)
    if size > 500:
        msg = f"Error, size = {size:d}"
        raise BadRequest(msg)
    group = get_visible_group(user, group_id)

    if group.photo:
        data = group.photo
    else:
        data = DEFAULT_GROUP_MUGSHOT

    if size:
        data = resize(data, size, size, mode=CROP)

    response = make_response(data)
    response.headers["content-type"] = "image/jpeg"
    response.headers.add("Cache-Control", "public, max-age=600")
    return response
