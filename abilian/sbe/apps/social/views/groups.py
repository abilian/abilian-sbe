from pathlib import Path

from flask import current_app, flash, jsonify, make_response, redirect, \
    render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user
from sqlalchemy import func
from werkzeug.exceptions import InternalServerError, NotFound

from abilian.core.extensions import db
from abilian.core.models.subjects import Group, User
from abilian.services import get_service
from abilian.services.image import CROP, resize
from abilian.services.security import security
from abilian.web import csrf
from abilian.web.views import default_view

from .social import social

DEFAULT_GROUP_MUGSHOT = (
    (Path(__file__).parent / ".." / ".." / ".." / "static" / "images" / "frog.jpg")
    .open("rb")
    .read()
)


@social.route("/groups/")
def groups() -> str:
    tab = request.args.get("tab", "all_groups")
    if tab == "all_groups":
        groups = Group.query.order_by(Group.name).all()
        if not security.has_role(current_user, "admin"):
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
    security = get_service("security")
    is_admin = current_user in group.admins
    if not is_admin and "security" in current_app.extensions:
        is_admin = security.has_role(current_user, "admin")

    return is_admin


@social.route("/groups/<int:group_id>")
@default_view(social, Group, "group_id")
def group_home(group_id):
    group = Group.query.get(group_id)
    ctx = {"group": group, "is_admin": is_admin(group)}
    return render_template("social/group.html", **ctx)


@social.route("/groups/<int:group_id>/json")
def group_json(group_id):
    members = Group.query.get(group_id).members
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
    group = Group.query.get(group_id)
    action = request.form.get("action")
    return_url = request.form.get("return_url")
    user_id = request.form.get("user", "").strip()

    membership_actions = frozenset(("add", "remove", "add-admin", "remove-admin"))

    if action not in {"join", "leave"}.union(membership_actions):
        raise ValueError(f"Unknown action: {action}")

    if action not in ("join", "leave"):
        assert is_admin(group)

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

        user = User.query.get(user_id)

        if action == "add":
            user.join(group)
        elif action == "remove":
            user.leave(group)
        elif action == "add-admin":
            if user not in group.admins:
                group.admins.append(user)
        elif action == "remove-admin":
            if user in group.admins:
                group.admins.remove(user)

    db.session.commit()

    if not return_url:
        return_url = url_for(".group_home", group_id=group_id)

    # TODO: security check
    return redirect(return_url)


@social.route("/groups/new")
def groups_new():
    # TODO later
    return

    # e = Env()
    # e.form = GroupForm()
    # return render_template("social/groups-new.html", **e)


@social.route("/groups/new", methods=["POST"])
def groups_new_post():
    # TODO later
    return

    # form = GroupForm()
    #
    # if form.validate():
    #     group = Group()
    #     form.populate_obj(group)
    #     db.session.add(group)
    #     db.session.commit()
    #     flash(_(u"Your new group has been created"), category='info')
    #     return redirect(url_for('.group_home', group_id=group.id))
    #
    # else:
    #     e = Env()
    #     e.form = form
    #     return render_template("social/groups-new.html", **e)


@social.route("/groups/<int:group_id>/mugshot")
def group_mugshot(group_id):
    # TODO: duplicated code (with user_mugshot). Extract common method.
    size = int(request.args.get("s", 55))
    if size > 500:
        raise ValueError(f"Error, size = {size:d}")
    group = Group.query.get(group_id)

    if not group:
        raise NotFound()

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


#
# Ad-hoc JSON endpoints, used by select boxes
#
@social.route("/groups/json")
def groups_json():
    q = request.args.get("q").replace("%", " ").lower()

    if not q or len(q) < 2:
        raise InternalServerError()

    query = Group.query
    # query = query.filter(func.lower(Group.name).like(q + "%"))
    query = query.order_by(func.lower(Group.name))
    all = query.all()

    result = {"results": [{"id": obj.id, "text": obj.name} for obj in all]}
    return jsonify(result)
