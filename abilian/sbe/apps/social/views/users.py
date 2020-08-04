import logging
import pkgutil
from html import escape
from typing import Dict, List

import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm
from flask import Response, flash, jsonify, redirect, render_template, request
from flask_login import current_user
from sqlalchemy.sql.expression import and_, asc, desc, func, nullslast, or_
from werkzeug.exceptions import InternalServerError

from abilian.core.extensions import db
from abilian.core.models.subjects import User
from abilian.i18n import _, _l
from abilian.sbe.apps.communities.models import Membership
from abilian.sbe.apps.social.forms import UserProfileForm, UserProfileViewForm
from abilian.sbe.apps.wall.presenters import ActivityEntryPresenter
from abilian.sbe.apps.wall.views import get_recent_entries
from abilian.services import get_service
from abilian.web import url_for
from abilian.web.filters import age
from abilian.web.views import ObjectEdit, default_view
from abilian.web.views.images import user_photo_url

from .social import social

logger = logging.getLogger(__name__)

DEFAULT_USER_MUGSHOT = pkgutil.get_data(
    "abilian.sbe", "static/images/silhouette_unknown.png"
)


def make_tabs(user: User) -> List[Dict[str, str]]:
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


@social.route("/users/")
def users() -> str:
    query = request.args.get("query")

    if query:
        query = query.replace("%", " ")
        q = or_(
            User.first_name.like("%" + query + "%"),
            User.last_name.like("%" + query + "%"),
        )
        users = User.query.filter(q).limit(100).all()
    else:
        users = User.query.limit(100).all()
    ctx = {"users": users}
    return render_template("social/users.html", **ctx)


@social.route("/users/dt_json")
def users_dt_json():
    """JSON call to fill a DataTable.

    Needs some refactoring.
    """
    args = request.args

    length = int(args.get("iDisplayLength", 0))
    start = int(args.get("iDisplayStart", 0))
    sort_col = int(args.get("iSortCol_0", 1))
    sort_dir = args.get("sSortDir_0", "asc")
    echo = int(args.get("sEcho", 0))
    search = args.get("sSearch", "").replace("%", "").lower()

    end = start + length

    query = User.query
    total_count = query.count()

    if search:
        # TODO: gérer les accents
        filter = or_(
            func.lower(User.first_name).like("%" + search + "%"),
            func.lower(User.last_name).like("%" + search + "%"),
        )
        query = query.filter(filter).reset_joinpoint()

    count = query.count()
    SORT_COLS = {
        1: [],  # will be set to [User.last_name, User.first_name]
        2: [User.created_at],
        3: [User.last_active],
    }
    columns = list(SORT_COLS.get(sort_col, []))
    columns.extend([func.lower(User.last_name), func.lower(User.first_name)])

    direction = asc if sort_dir == "asc" else desc
    order_by = [direction(column) for column in columns]

    # sqlite does not support 'NULLS FIRST|LAST' in ORDER BY clauses
    engine = query.session.get_bind(User.__mapper__)
    if engine.name != "sqlite":
        order_by[0] = nullslast(order_by[0])

    query = query.order_by(*order_by)

    users = query.slice(start, end).all()

    data = []
    MUGSHOT_SIZE = 45
    for user in users:
        # TODO: this should be done on the browser.
        user_url = url_for(".user", user_id=user.id)
        mugshot = user_photo_url(user, size=MUGSHOT_SIZE)
        name = escape(user.name or "")

        cell0 = (
            '<a href="{url}"><img src="{src}" width="{size}" height="{size}">'
            "</a>".format(url=user_url, src=mugshot, size=MUGSHOT_SIZE)
        )
        cell1 = '<div class="info"><a href="{user_url}">{name}</a> ' "</div>".format(
            **locals()
        )
        cell2 = age(user.created_at)
        cell3 = age(user.last_active)

        cell4 = ""  # TODO: follow / unfollow?
        data.append([cell0, cell1, cell2, cell3])

    result = {
        "sEcho": echo,
        "iTotalRecords": total_count,
        "iTotalDisplayRecords": count,
        "aaData": data,
    }
    return jsonify(result)


@social.route("/users/<int:user_id>")
@default_view(social, User, "user_id")
def user(user_id: int) -> str:
    security = get_service("security")
    user = User.query.get(user_id)

    # FIXME: use user profiles
    view_form = UserProfileViewForm(obj=user)

    communities = [m.community for m in user.communautes_membership]
    if current_user != user and (not security.has_role(current_user, "manager")):
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
    security = get_service("security")
    if not security:
        return True

    # TODO: introduce a "self" role?
    return (user == current_user) or security.has_role(current_user, "admin")


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
        logger.error(log_msg, exc_info=True, extra={"stack": True})
        flash(_("Error occured"), "error")
        return self.redirect_to_view()


social.route("/users/<int:user_id>/edit")(UserProfileEdit.as_view("user_edit"))


@social.route("/users/<int:user_id>", methods=["POST"])
def user_post(user_id):
    user = User.query.get(user_id)
    action = request.form.get("action")
    return_url = request.form.get("return_url")

    if action == "follow":
        current_user.follow(user)
    elif action == "unfollow":
        current_user.unfollow(user)
    else:
        raise Exception("Should not happen")
    db.session.commit()

    if return_url:
        # TODO: security check
        return redirect(return_url)
    else:
        return redirect(url_for(".user_view", user_id=user_id))


#
# Ad-hoc JSON endpoints, used by select boxes
#
@social.route("/users/json")
def users_json():
    q = request.args.get("q").replace("%", " ").lower()

    if not q or len(q) < 2:
        raise InternalServerError()

    query = User.query.filter(
        or_(
            func.lower(User.first_name).like(q + "%"),
            func.lower(User.last_name).like(q + "%"),
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
