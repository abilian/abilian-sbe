# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from pathlib import Path

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
from flask_login import current_user
from werkzeug.exceptions import Forbidden, NotFound

from abilian.core.extensions import db
from abilian.core.models.subjects import Group, User
from abilian.services.image import CROP, resize
from abilian.services.security import is_site_admin
from abilian.web import csrf
from abilian.web.views import default_view

from .social import social

DEFAULT_GROUP_MUGSHOT = (
    Path(__file__).parent / ".." / ".." / ".." / "static" / "images" / "frog.jpg"
).read_bytes()


@social.route("/groups/")
def groups() -> str:
    tab = request.args.get("tab", "all_groups")
    if tab == "all_groups":
        groups = Group.query.order_by(Group.name).all()
        if not is_site_admin():
            groups = [
                group
                for group in groups
                if group.public or current_user in group.members
            ]
    else:
        groups = current_user.groups
        groups.sort(key=lambda x: x.name)

    return render_template("social/groups.html", groups=groups)


def is_admin(group):
    """May the current user administer `group`?

    Group administrators are a relationship on `Group`, not role assignments,
    so this cannot be `has_role(user, ADMIN, group)` yet.
    """
    if current_user in group.admins:
        return True
    return "security" in current_app.extensions and is_site_admin()


@social.route("/groups/<int:group_id>")
@default_view(social, Group, "group_id")
def group_home(group_id):
    group = Group.query.get_or_404(group_id)
    ctx = {"group": group, "is_admin": is_admin(group)}
    return render_template("social/group.html", **ctx)


@social.route("/groups/<int:group_id>/json")
def group_json(group_id):
    members = Group.query.get_or_404(group_id).members
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
def group_post(group_id):
    group = Group.query.get_or_404(group_id)
    action = request.form.get("action")
    return_url = request.form.get("return_url")
    user_id = request.form.get("user", "").strip()

    membership_actions = frozenset(("add", "remove", "add-admin", "remove-admin"))

    if action not in {"join", "leave"} | membership_actions:
        msg = f"Unknown action: {action}"
        raise ValueError(msg)

    # Everything but join and leave writes somebody else's membership, and
    # add-admin writes who may do that. This was an `assert`, which `python -O`
    # compiles out entirely and which raises a 500 rather than refusing when it
    # is compiled in.
    if action not in ("join", "leave") and not is_admin(group):
        raise Forbidden

    if action == "join":
        current_user.join(group)
    elif action == "leave":
        current_user.leave(group)

    elif action in membership_actions:
        try:
            user_id = int(user_id)
        except ValueError:
            flash(_("Error: No user selected"), "error")
            return redirect(url_for(".group_home", group_id=group_id))

        user = User.query.get_or_404(user_id)

        match action:
            case "add":
                user.join(group)
            case "remove":
                user.leave(group)
            case "add-admin":
                if user not in group.admins:
                    group.admins.add(user)
            case "remove-admin":
                if user in group.admins:
                    group.admins.remove(user)

    db.session.commit()

    if not return_url:
        return_url = url_for(".group_home", group_id=group_id)

    # TODO: security check
    return redirect(return_url)


@social.route("/groups/<int:group_id>/mugshot")
def group_mugshot(group_id):
    # TODO: duplicated code (with user_mugshot). Extract common method.
    size = int(request.args.get("s", 55))
    if size > 500:
        msg = f"Error, size = {size:d}"
        raise ValueError(msg)
    group = Group.query.get(group_id)

    if not group:
        raise NotFound

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
