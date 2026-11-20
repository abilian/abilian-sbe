# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import contextlib
import smtplib
from collections import Counter
from functools import cache, wraps
from io import BytesIO
from operator import attrgetter
from time import gmtime, strftime
from typing import TYPE_CHECKING, Any

import openpyxl
import sqlalchemy as sa
import sqlalchemy.sql.functions
from flask import (
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from openpyxl.cell import WriteOnlyCell
from werkzeug.exceptions import BadRequest, NotFound
from werkzeug.local import LocalProxy
from whoosh.searching import Hit

from abilian.core.extensions import db
from abilian.core.extensions.login import authenticated, authenticated_user
from abilian.core.models.subjects import User, UserQuery
from abilian.core.signals import activity
from abilian.core.util import unwrap
from abilian.i18n import _, _l, _n
from abilian.sbe.apps.communities import security as community_security
from abilian.sbe.apps.communities.actions import register_actions
from abilian.sbe.apps.communities.blueprint import CommunityBlueprint
from abilian.sbe.apps.communities.decorators import can_manage, is_site_admin
from abilian.sbe.apps.communities.forms import CommunityForm
from abilian.sbe.apps.communities.invitations import send_invitation
from abilian.sbe.apps.communities.models import (
    DEFAULT_IMAGE,
    DEFAULT_IMAGE_MD5,
    MANAGER,
    MEMBER,
    Community,
    Membership,
    MembershipRequest,
)
from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.documents.repository import content_repository
from abilian.services import security as site_security
from abilian.services.activity import ActivityEntry
from abilian.services.security import Role
from abilian.web import csrf, views
from abilian.web.action import Endpoint
from abilian.web.listing import Listing, by_name
from abilian.web.nav import BreadcrumbItem
from abilian.web.views import images as image_views

if TYPE_CHECKING:
    from collections.abc import Callable

    from flask.blueprints import BlueprintSetupState
    from werkzeug.wrappers.response import Response

    from abilian.sbe.apps.communities.presenters import CommunityPresenter

__all__ = ["BaseCommunityView", "communities", "default_view_kw", "route", "tab"]


communities = CommunityBlueprint(
    "communities",
    __name__,
    set_community_id_prefix=False,
    template_folder="../templates",
)
route = communities.route
add_url = communities.add_url_rule
communities.record_once(register_actions)


@communities.record_once
def register_context_processors(state: BlueprintSetupState) -> None:
    @state.app.context_processor
    def communities_context_processor() -> dict[str, Any]:
        # `can_manage_community` is supplied here rather than by each view that
        # renders a members table. Left to the views, the wizard's three did not,
        # and the header and the row disagreed about how many columns there were.
        #
        # Lazy, because every template renders with this context, the error pages
        # included, and those run after the session that holds `g.community` is
        # gone: asking the security service there turned a 500 into a raw one.
        # Cached for this render, as each row of a members table reads it.
        return {
            "community_image_url": image_url,  # url for a community image
            "can_manage_community": LocalProxy(cache(_can_manage_current_community)),
        }


def _can_manage_current_community() -> bool:
    return hasattr(g, "community") and community_security.can_manage(
        authenticated_user(), g.community
    )


def tab(tab_name: str) -> Callable:
    """Decorator for view functions to set the current "section" this view
    belongs to."""

    def decorator(f):
        @wraps(f)
        def set_current_tab(*args: Any, **kwargs: Any) -> str | Response:
            g.current_tab = tab_name
            return f(*args, **kwargs)

        return set_current_tab

    return decorator


def default_view_kw(
    kw: dict[str, int], obj: Any, obj_type: str, obj_id: int, **kwargs: Any
) -> dict[str, Any]:
    """Helper for using :func:`abilian.web.views.default_view` on objects that
    belongs to a community. This function should be used as `kw_func`::

    @default_view(blueprint, Model, kw_func=default_view_kw)
    @blueprint.route("/<object_id>")
    def view():
        ...
    """
    is_community = obj_type == Community.entity_type
    community_id = kw.get("community_id")

    if is_community or community_id is None:
        # when it's a community, default_view sets community_id to 'id', we want to
        # override with the slug value.
        if obj:
            if isinstance(obj, (Hit, dict)):
                community_id = obj.get("slug" if is_community else "community_slug")
            elif is_community:
                community_id = obj.slug
            elif community_id is None and hasattr(obj, "community"):
                with contextlib.suppress(AttributeError):
                    community_id = obj.community.slug

    if community_id is not None:
        kw["community_id"] = community_id
    else:
        msg = "Cannot find community_id value"
        raise ValueError(msg)

    return kw


#
# Routes
#
@route("/")
@authenticated
def index(user: User) -> str:
    query = Community.query
    sort_order = request.args.get("sort", "").strip()
    if not sort_order:
        sort_order = session.get("sort_communities_order", "alpha")

    if sort_order == "activity":
        query = query.order_by(Community.last_active_at.desc())
    else:
        query = query.order_by(Community.name)

    session["sort_communities_order"] = sort_order

    search = request.args.get("q", "").strip()
    if search:
        query = query.filter(
            sa.func.lower(Community.name).contains(search.lower(), autoescape=True)
        )

    # Not passed to the template: `is_admin` was one name for two different
    # questions there -- site-wide here, group-scoped on a group's page, gone
    # since -- which is how `g.is_manager` went wrong one layer down. The
    # template asks `is_site_admin()` by name instead.
    is_admin = site_security.is_site_admin(user)
    if not is_admin:
        # Filter with permissions
        query = query.join(Membership).filter(Membership.user == user)

    ctx = {
        "my_communities": query.all(),
        "sort_order": sort_order,
        "search": search,
    }
    return render_template("community/home.html", **ctx)


@route("/<string:community_id>/")
@views.default_view(communities, Community, "community_id", kw_func=default_view_kw)
def community() -> Response:
    return redirect(url_for("wall.index", community_id=g.community.slug))


# edit views
class BaseCommunityView:
    Model = Community
    pk = "community_id"
    Form = CommunityForm
    decorators = [is_site_admin]
    view_endpoint = ""

    def init_object(self, args: tuple[()], kwargs: dict) -> tuple[tuple[()], dict]:
        self.obj = g.community._model
        return args, kwargs

    def view_url(self) -> str:
        return url_for(self.view_endpoint, community_id=self.obj.slug)

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()

        image = self.obj.image
        if image and "community" in g:
            image.url = image_url(self.obj, s=500)
            kwargs["image"] = image

        return kwargs


class CommunityEdit(BaseCommunityView, views.ObjectEdit[Community, CommunityForm]):
    template = "community/edit.html"
    title = _l("Edit community")
    decorators = (*views.ObjectEdit.decorators, can_manage, tab("settings"))

    def breadcrumb(self) -> BreadcrumbItem:
        url = Endpoint("communities.settings", community_id=g.community.slug)
        return BreadcrumbItem(label=_("Settings"), icon="cog", url=url)

    def before_populate_obj(self) -> None:
        form = self.form
        name = form.name.data
        if name != self.obj.name:
            self.obj.rename(name)

        del form.name

        type = form.type.data
        if type != self.obj.type:
            self.obj.type = type
            self.obj.update_roles_on_folder()
        del form.type


add_url(
    "/<string:community_id>/settings",
    view_func=CommunityEdit.as_view(
        "settings",
        view_endpoint=".community",
        message_success=_l("Community settings saved successfully."),
    ),
)


class CommunityCreate(views.ObjectCreate[Community, CommunityForm], CommunityEdit):
    title = _l("Create community")
    decorators = (*views.ObjectCreate.decorators, is_site_admin)
    template = "community/new.html"
    #: Who will run it: the person picked, or else whoever makes it.
    manager: User | None = None

    def validate(self) -> bool:
        if not super().validate():
            return False
        manager_id = request.form.get("manager", type=int)
        if manager_id is not None:
            self.manager = User.query.get(manager_id)
            if self.manager is None:
                msg = f"Unknown manager: {manager_id}"
                raise BadRequest(msg)
        return True

    def breadcrumb(self) -> BreadcrumbItem:
        return BreadcrumbItem(label=_("Create new community"))

    def commit_success(self) -> None:
        """The person picked manages it, or else whoever creates it.

        Recorded as a membership like anyone else's rather than as a special
        case in a predicate. It used to be the latter -- `is_manager` alone
        granted to `community.creator` -- so a creator was offered manage
        actions and then refused by the views behind them, and "who manages
        this" could not be read off the member list or revoked through it.

        After the commit, not in `after_populate_obj`: adding a membership
        fires the signal that grants the corresponding role on the community's
        folder, and inside `no_autoflush` that folder has no id yet.
        """
        super().commit_success()
        manager = self.manager or self.obj.creator
        if manager:
            self.obj.set_membership(manager, MANAGER)
            db.session.commit()

    def message_success(self):
        return _("Community %(name)s created successfully", name=self.obj.name)


add_url("/new", view_func=CommunityCreate.as_view("new", view_endpoint=".community"))


class CommunityDelete(BaseCommunityView, views.ObjectDelete[Community, CommunityForm]):
    get_form_kwargs = views.ObjectDelete.get_form_kwargs


add_url(
    "/<string:community_id>/destroy",
    methods=["POST"],
    view_func=CommunityDelete.as_view(
        "delete", message_success=_l("Community destroyed.")
    ),
)

# Community Image
route("/_default_image")(
    image_views.StaticImageView.as_view(
        "community_default_image", set_expire=True, image=DEFAULT_IMAGE
    )
)


class CommunityImageView(image_views.BlobView):
    id_arg = "blob_id"

    def prepare_args(self, args, kwargs):
        community = g.community
        if not community:
            raise NotFound

        kwargs[self.id_arg] = community.image.id
        # image = open(join(dirname(__file__), "data", "community.png"), 'rb')
        return super().prepare_args(args, kwargs)


image = CommunityImageView.as_view("image", max_size=500, set_expire=True)
route("/<string:community_id>/image")(image)


def image_url(community: Community | CommunityPresenter, **kwargs: Any) -> str:
    """Return proper URL for image url."""
    if not community or not community.image:
        kwargs["md5"] = DEFAULT_IMAGE_MD5
        return url_for("communities.community_default_image", **kwargs)

    kwargs["community_id"] = community.slug
    kwargs["md5"] = community.image.md5
    return url_for("communities.image", **kwargs)


def _members_query() -> UserQuery:
    """Helper used in members views."""
    last_activity_date = sa.sql.functions.max(ActivityEntry.happened_at).label(
        "last_activity_date"
    )
    memberships = (
        User.query.options(sa.orm.undefer(User.photo))
        .join(Membership)
        .outerjoin(
            ActivityEntry,
            sa.sql.and_(
                ActivityEntry.actor_id == User.id,
                ActivityEntry.target_id == Membership.community_id,
            ),
        )
        .filter(Membership.community == g.community, User.can_login == True)
        .add_columns(Membership.id, Membership.role, last_activity_date)
        .group_by(User, Membership.id, Membership.role)
        .order_by(User.last_name.asc(), User.first_name.asc())
    )

    return memberships


@route("/<string:community_id>/members")
@tab("members")
def members() -> str:
    g.breadcrumb.append(
        BreadcrumbItem(
            label=_("Members"),
            url=Endpoint("communities.members", community_id=g.community.slug),
        )
    )
    community_threads_users = [thread.creator for thread in g.community.threads]
    threads_count = Counter(community_threads_users)
    sort_keys = {
        "name": lambda row: by_name(row[0]),
        "posts": lambda row: threads_count[row[0]],
        "activity": lambda row: (row[3] is not None, row[3]),
        "role": lambda row: (str(row[2]), by_name(row[0])),
    }
    rows = _members_query().all()
    managers = [row for row in rows if str(row[2]) == "manager"]
    only_managers = request.args.get("role") == "manager"

    def text(row: tuple) -> str:
        return f"{row[0].name} {row[0].email}"

    listing, memberships = Listing.from_rows(
        managers if only_managers else rows, sort_keys, "name", text=text
    )

    ctx = {
        "listing": listing,
        "memberships": memberships,
        "threads_count": threads_count,
        "only_managers": only_managers,
        "requests": g.community._model.membership_requests,
        "counts": {
            name: sum(listing.matches(text(row)) for row in group)
            for name, group in (("all", rows), ("managers", managers))
        },
    }
    return render_template("community/members.html", **ctx)


@route("/<string:community_id>/members", methods=["POST"])
@csrf.protect
@can_manage
def members_post() -> Response:
    community = g.community._model
    action = request.form.get("action")
    if action in SELECTION_ACTIONS:
        return _act_on_selection(community, action)
    if action in {"accept-request", "refuse-request"}:
        return _answer_request(community, action == "accept-request")

    user_id = request.form.get("user")
    if not user_id:
        flash(_("You must provide a user."), "error")
        return redirect(url_for(".members", community_id=community.slug))
    user_id = int(user_id)
    user = User.query.get_or_404(user_id)

    match action:
        case "add-user-role" | "set-user-role":
            role = request.form["role"].lower()
            if role != MANAGER and _leaves_no_manager(community, {user.id}):
                return _refused_last_manager(community)

            community.set_membership(user, role)

            if action == "add-user-role":
                app = unwrap(current_app)
                activity.send(app, actor=user, verb="join", object=community)

            db.session.commit()
            return redirect(url_for(".members", community_id=community.slug))

        case "delete":
            membership_id = int(request.form["membership"])
            membership = Membership.query.get_or_404(membership_id)
            if membership.user_id != user_id:
                msg = "This membership is not the user's"
                raise BadRequest(msg)

            if _leaves_no_manager(community, {user.id}):
                return _refused_last_manager(community)
            community.remove_membership(user)

            app = unwrap(current_app)
            activity.send(app, actor=user, verb="leave", object=community)

            db.session.commit()
            return redirect(url_for(".members", community_id=community.slug))

    msg = f"Unknown action: {action!r}"
    raise BadRequest(msg)


def _answer_request(community: Community, accepted: bool) -> Response:
    """A request to join, answered: its person made a member and told so, or not."""
    asking = MembershipRequest.query.filter_by(
        id=request.form.get("request", type=int), community_id=community.id
    ).first_or_404()
    user = asking.user
    db.session.delete(asking)
    members = redirect(url_for(".members", community_id=community.slug))
    if not accepted:
        db.session.commit()
        flash(_("%(name)s will not join the community.", name=user.name))
        return members

    community.set_membership(user, MEMBER)
    activity.send(unwrap(current_app), actor=user, verb="join", object=community)
    db.session.commit()
    try:
        send_invitation(user, community, authenticated_user(), "")
    except (smtplib.SMTPException, OSError):
        flash(
            _("%(name)s is a member, but could not be told by e-mail.", name=user.name),
            "warning",
        )
        return members
    flash(_("%(name)s is a member now, and told so.", name=user.name), "success")
    return members


#: What the members' selection does: the role it gives, or None to remove them.
def _leaves_no_manager(community: Community, user_ids: set[int]) -> bool:
    """Whether taking `user_ids` from the community's managers leaves it with none,
    where it had some: no one inside could run it any more."""
    managers = {m.user_id for m in community.memberships if m.role == MANAGER}
    return bool(managers) and managers <= user_ids


def _refused_last_manager(community: Community) -> Response:
    flash(
        _("A community keeps at least one manager: name another one first."),
        "error",
    )
    return redirect(url_for(".members", community_id=community.slug))


SELECTION_ACTIONS = {
    "selection-managers": MANAGER,
    "selection-members": MEMBER,
    "selection-remove": None,
}


def _act_on_selection(community: Community, action: str) -> Response:
    """Give the selected members a role, or remove them: only members of
    `community`, whatever else is posted."""
    ids = request.form.getlist("selected", type=int)
    members = (
        User.query.join(Membership, Membership.user_id == User.id)
        .filter(Membership.community_id == community.id, User.id.in_(ids))
        .all()
    )
    role = SELECTION_ACTIONS[action]
    if role != MANAGER and _leaves_no_manager(community, {u.id for u in members}):
        return _refused_last_manager(community)
    app = unwrap(current_app)
    for user in members:
        if role is None:
            community.remove_membership(user)
            activity.send(app, actor=user, verb="leave", object=community)
        else:
            community.set_membership(user, role)
    db.session.commit()
    flash(_n("%(num)d member changed.", "%(num)d members changed.", len(members)))
    return redirect(url_for(".members", community_id=community.slug))


MEMBERS_EXPORT_HEADERS = [
    _l("Name"),
    _l("email"),
    _l("Last activity in this community"),
    _l("Role"),
]

MEMBERS_EXPORT_ATTRS = ["User", "User.email", "last_activity_date", "role"]

HEADER_FONT = openpyxl.styles.Font(bold=True)
HEADER_ALIGN = openpyxl.styles.Alignment(
    horizontal="center", vertical="top", wrapText=True
)
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@route("/<string:community_id>/members/excel")
@tab("members")
def members_excel_export():
    community = g.community
    attributes = [attrgetter(a) for a in MEMBERS_EXPORT_ATTRS]
    BaseModel = db.Model
    wb = openpyxl.Workbook()

    if wb.worksheets:
        wb.remove_sheet(wb.active)

    ws_title = _("%(community)s members", community=community.name)
    ws_title = ws_title.strip()
    if len(ws_title) > 31:
        # sheet title cannot exceed 31 char. max length
        ws_title = f"{ws_title[:30]}…"
    ws = wb.create_sheet(title=ws_title)
    cells = []

    cols_width = []
    for label in MEMBERS_EXPORT_HEADERS:
        value = str(label)
        cell = WriteOnlyCell(ws, value=value)
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
        cells.append(cell)
        cols_width.append(len(value) + 1)

    ws.append(cells)

    for membership_info in _members_query().all():
        cells = []
        for col, getter in enumerate(attributes):
            with contextlib.suppress(AttributeError):
                value = getter(membership_info)

            if isinstance(value, (BaseModel, Role)):
                value = str(value)

            cell = WriteOnlyCell(ws, value=value)
            cells.append(value)

            # estimate width
            value = str(cell.value)
            width = max(len(l) for l in value.split("\n")) + 1
            cols_width[col] = max(width, cols_width[col])

        ws.append(cells)

    # adjust columns width
    MIN_WIDTH = 3
    MAX_WIDTH = openpyxl.utils.units.BASE_COL_WIDTH * 4

    for idx, width in enumerate(cols_width, 1):
        letter = openpyxl.utils.get_column_letter(idx)
        width = min(max(width, MIN_WIDTH), MAX_WIDTH)
        ws.column_dimensions[letter].width = width

    fd = BytesIO()
    wb.save(fd)
    fd.seek(0)

    response = current_app.response_class(fd, mimetype=XLSX_MIME)

    filename = (
        f"{community.slug}-members-{strftime('%d:%m:%Y-%H:%M:%S', gmtime())}.xlsx"
    )
    response.headers["content-disposition"] = f'attachment;filename="{filename}"'

    return response


#
# Hack to redirect from urls used by the search engine.
#


@route("/doc/<int:doc_id>")
@authenticated
def doc(user: User, doc_id: int) -> Response:
    doc = Document.query.get(doc_id)

    # Not found either for a user who may not read it: the redirect would
    # tell them which community the document is in.
    if doc is None or not content_repository.has_access(user, doc):
        raise NotFound

    folder = doc.parent
    while True:
        parent = folder.parent
        if parent.is_root_folder:
            break
        folder = parent

    target_community = Community.query.filter(Community.folder_id == folder.id).one()
    location = url_for(
        "documents.document_view", community_id=target_community.slug, doc_id=doc.id
    )
    return redirect(location)
