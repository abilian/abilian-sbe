import difflib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from urllib.parse import quote

import sqlalchemy as sa
from flask import current_app, flash, g, make_response, redirect, \
    render_template, request
from flask_login import current_user
from markdown import markdown
from markupsafe import Markup
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import NotFound
from werkzeug.wrappers import Response
from whoosh.searching import Hit

from abilian.core.extensions import db
from abilian.core.signals import activity
from abilian.core.util import unwrap
from abilian.i18n import _, _l, _n
from abilian.sbe.apps.communities.blueprint import Blueprint
from abilian.sbe.apps.communities.common import object_viewers
from abilian.sbe.apps.communities.models import Community
from abilian.sbe.apps.communities.presenters import CommunityPresenter
from abilian.sbe.apps.communities.views import \
    default_view_kw as community_dv_kw
from abilian.services.security.models import Permission
from abilian.services.viewtracker import viewtracker
from abilian.web import csrf
from abilian.web.action import Endpoint, actions
from abilian.web.nav import BreadcrumbItem
from abilian.web.util import url_for
from abilian.web.views import ObjectCreate, ObjectEdit, ObjectView, \
    default_view

from .forms import WikiPageForm
from .models import WikiPage, WikiPageAttachment, WikiPageRevision

wiki = Blueprint("wiki", __name__, url_prefix="/wiki", template_folder="templates")
route = wiki.route


@wiki.url_value_preprocessor
def init_wiki_values(endpoint: str, values: Dict[Any, Any]) -> None:
    g.current_tab = "wiki"

    endpoint = Endpoint("wiki.index", community_id=g.community.slug)
    g.breadcrumb.append(BreadcrumbItem(label=_l("Wiki"), url=endpoint))

    title = request.args.get("title", "").strip()
    if title and title != "Home":
        url = Endpoint("wiki.page", community_id=g.community.slug, title=title)
        g.breadcrumb.append(BreadcrumbItem(label=title, url=url))


@route("/")
def index() -> Response:
    return redirect(url_for(".page", title="Home", community_id=g.community.slug))


def wiki_page_default_view_kw(kw, obj, obj_type, obj_id, **kwargs):
    kw = community_dv_kw(kw, obj, obj_type, obj_id, **kwargs)
    title = kwargs.get("title")
    if title is None:
        if isinstance(obj, (Hit, dict)):
            title = obj.get("name")
        else:
            title = obj.title
        kw["title"] = title
    return kw


#
# Page level (all functions prefixed by 'page_').
#
class BasePageView:
    Model = WikiPage
    pk = "title"
    Form = WikiPageForm
    base_template = "wiki/_base.html"
    view_endpoint = ""

    @property
    def is_home_page(self):
        return self.obj is not None and self.obj.title == "Home"

    @property
    def template_kwargs(self) -> Dict[str, Union[WikiPageForm, WikiPage]]:
        """Template render arguments.

        You can override `base_template` for instance. Only `view` and
        `form` cannot be overriden.
        """
        kw = super().template_kwargs
        kw["page"] = self.obj
        kw["viewers"] = object_viewers(self.obj)
        return kw

    def init_object(
        self, args: Tuple[Any], kwargs: Dict[str, Any]
    ) -> Tuple[Tuple[Any], Dict[str, Any]]:
        title = kwargs["title"] = request.args["title"].strip()
        if title:
            try:
                self.obj = get_page_by_title(title)
            except NoResultFound:
                if title == "Home":
                    self.obj = create_home_page()
                else:
                    flash(
                        _("This page doesn't exit. You must create it first."),
                        "warning",
                    )
                    url = url_for(
                        ".page_new", title=title, community_id=g.community.slug
                    )
                    self.redirect(url)
            actions.context["object"] = self.obj
        return args, kwargs

    def index_url(self):
        return url_for(".index", community_id=g.community.slug)

    def view_url(self) -> str:
        return url_for(
            self.view_endpoint, community_id=g.community.slug, title=self.obj.title
        )


class PageView(BasePageView, ObjectView):
    template = "wiki/page.html"
    view_endpoint = ".page"
    decorators = [
        default_view(wiki, WikiPage, id_attr=None, kw_func=wiki_page_default_view_kw)
    ]

    def init_object(
        self, args: Tuple[Any], kwargs: Dict[str, Any]
    ) -> Tuple[Tuple[Any], Dict[str, Any]]:
        args, kwargs = BasePageView.init_object(self, args, kwargs)
        if not self.obj:
            title = kwargs["title"]
            if title == "Home":
                self.obj = create_home_page()
            else:
                url = url_for(".page_edit", title=title, community_id=g.community.slug)
                return redirect(url)

        actions.context["object"] = self.obj
        viewtracker.record_hit(entity=self.obj, user=current_user)
        return args, kwargs


route("/page/")(PageView.as_view("page"))


class PageViewers(PageView):

    template = "wiki/page_readers.html"


route("/viewers")(PageViewers.as_view("page_viewers"))


class PageEdit(BasePageView, ObjectEdit):
    # template = 'wiki/page_edit.html'
    title = _("Edit page")
    last_revision: int = None
    _message_success = _l("Wiki page successfully edited.")

    def init_object(
        self, args: Tuple[Any], kwargs: Dict[str, Any]
    ) -> Tuple[Tuple, Dict[str, Any]]:
        if request.method != "POST":
            return super().init_object(args, kwargs)

        page_id = request.form.get("page_id") or None
        if page_id is not None:
            page_id = int(page_id)
            self.obj = WikiPage.query.get_or_404(page_id)
            actions.context["object"] = self.obj

        return args, kwargs

    def get_form_kwargs(self) -> Dict[str, Union[WikiPage, Permission, int]]:
        kwargs = ObjectEdit.get_form_kwargs(self)
        kwargs["page_id"] = kwargs["last_revision_id"] = None
        if self.obj is not None and self.obj.id:
            # if no 'id', then it's a new object (PageCreate). We shouldn't call
            # obj.last_revision, since it will issue a flush (thus creating obj and
            # the 1st revision, resulting in an "edit conflict")
            kwargs["page_id"] = self.obj.id
            kwargs["last_revision_id"] = self.obj.last_revision.id
        return kwargs

    def prepare_args(
        self, args: Tuple[Any], kwargs: Dict[str, Any]
    ) -> Tuple[Tuple, Dict[str, Any]]:
        super().prepare_args(args, kwargs)
        last_revision_id = self.form.last_revision_id.data
        if last_revision_id:
            self.last_revision = WikiPageRevision.query.filter(
                WikiPageRevision.page == self.obj,
                WikiPageRevision.id == last_revision_id,
            ).first()
        return args, kwargs

    def before_populate_obj(self) -> None:
        self.redirect_if_no_change()
        form = self.form
        self.obj.create_revision(form.body_src.data, form.message.data)

    # FIXME: does nothing !
    def redirect_if_no_change(self) -> Optional[Response]:
        form = self.form
        if all(f.data == f.object_data for f in (form.title, form.body_src)):
            flash(_("You didn't make any change to this page."))
            return self.redirect(url_for(self.obj))
        return None

    @property
    def activity_target(self) -> Union[CommunityPresenter, Community]:
        return self.obj.community

    def form_invalid(self):
        is_conflict = self.form.errors.pop("last_revision_id", None)
        if not self.form.errors and is_conflict is not None:
            # no other error on form, just edit conflict: show new text
            self.form.last_revision_id.errors = []
            field = self.form.body_src
            current = self.obj.last_revision
            self.form.last_revision_id.data = current.id  # update edited revision
            self.redirect_if_no_change()  # same edition? don't bother

            if self.last_revision.body_src == current.body_src and self.form.validate():
                # only title change? cannot show diff: save if valid
                return self.form_valid()
            else:
                edited_src = field.data
                field.data = current.body_src
                edited_diff = [
                    l
                    for l in difflib.ndiff(
                        self.last_revision.body_src.splitlines(True),
                        edited_src.splitlines(True),
                    )
                    if not l[0] == "?"
                ]
                current_diff = [
                    l
                    for l in difflib.ndiff(
                        self.last_revision.body_src.splitlines(True),
                        current.body_src.splitlines(True),
                    )
                    if not l[0] == "?"
                ]
                ctx = {
                    "current": current,
                    "current_diff": current_diff,
                    "edited_diff": edited_diff,
                }
                field.errors.append(
                    Markup(render_template("wiki/edit_conflict_error.html", **ctx))
                )

        return None


route("/edit")(PageEdit.as_view("page_edit", view_endpoint=".page"))


class PageCreate(PageEdit, ObjectCreate):
    title = _l("Create page")
    _message_success = _l("Wiki page successfully created.")

    get_form_kwargs = ObjectCreate.get_form_kwargs

    def init_object(
        self, args: Tuple[Any], kwargs: Dict[str, Any]
    ) -> Tuple[Tuple[Any], Dict[str, Any]]:
        args, kwargs = ObjectCreate.init_object(self, args, kwargs)
        self.obj.community = g.community
        session = sa.orm.object_session(self.obj)
        if session:
            sa.orm.session.make_transient(self.obj)
            for rev in self.obj.revisions:
                sa.orm.session.make_transient(rev)
        return args, kwargs


route("/new")(PageCreate.as_view("page_new", view_endpoint=".page"))


@route("/source/")
def page_source() -> Union[str, Response]:
    title = request.args["title"].strip()
    try:
        page = get_page_by_title(title)
    except NoResultFound:
        return redirect(
            url_for(".page_edit", title=title, community_id=g.community.slug)
        )

    actions.context["object"] = page
    return render_template("wiki/source.html", page=page)


@route("/changes/")
def page_changes() -> Union[str, Response]:
    title = request.args["title"].strip()
    try:
        page = get_page_by_title(title)
    except NoResultFound:
        url = url_for(".page_edit", title=title, community_id=g.community.slug)
        return redirect(url)
    revisions = page.revisions
    revisions = sorted(revisions, key=lambda x: -x.number)
    actions.context["object"] = page
    return render_template("wiki/changes.html", page=page, revisions=revisions)


@route("/compare/")
def page_compare() -> Union[str, Response]:
    title = request.args["title"].strip()
    try:
        page = get_page_by_title(title)
    except NoResultFound:
        return redirect(
            url_for(".page_edit", title=title, community_id=g.community.slug)
        )
    revisions = page.revisions
    revisions = sorted(revisions, key=lambda x: x.number)
    revs_to_compare = []
    for arg in request.args:
        if arg.startswith("rev"):
            revs_to_compare.append(int(arg[3:]))
    if len(revs_to_compare) != 2:
        flash(_("You must check exactly 2 revisions."), "error")
        url = url_for(".page_changes", title=title, community_id=g.community.slug)
        return redirect(url)

    revs_to_compare.sort()
    from_rev = revisions[revs_to_compare[0]]
    to_rev = revisions[revs_to_compare[1]]
    assert from_rev.number == revs_to_compare[0]
    assert to_rev.number == revs_to_compare[1]

    from_lines = from_rev.body_src.splitlines(1)
    to_lines = to_rev.body_src.splitlines(1)

    differ = difflib.Differ(charjunk=difflib.IS_CHARACTER_JUNK)
    diff = differ.compare(from_lines, to_lines)
    diff_lines = [line for line in diff if not line.startswith("?")]

    actions.context["object"] = page
    ctx = {"page": page, "diff": diff_lines, "rev1": from_rev, "rev2": to_rev}
    return render_template("wiki/compare.html", **ctx)


@route("/delete/", methods=["POST"])
def page_delete() -> Response:
    title = request.form["title"].strip()
    try:
        page = get_page_by_title(title)
    except NoResultFound:
        flash(_("This page doesn't exist"), "error")
        return redirect(url_for(".index", community_id=g.community.slug))

    db.session.delete(page)

    app = unwrap(current_app)
    community = g.community._model
    activity.send(app, actor=current_user, verb="delete", object=page, target=community)

    db.session.commit()
    flash(_("Page %(title)s deleted.", title=title))
    return redirect(url_for(".index", community_id=g.community.slug))


@route("/attachments")
def attachment_download() -> Response:
    title = request.args["title"].strip()
    attachment_id = int(request.args["attachment"])
    try:
        page = get_page_by_title(title)
    except NoResultFound:
        raise NotFound()

    attachment = WikiPageAttachment.query.get(attachment_id)
    assert attachment is not None
    assert attachment.wikipage is page

    response = make_response(attachment.content)
    response.headers["content-length"] = attachment.content_length
    response.headers["content-type"] = attachment.content_type
    filename = quote(attachment.name.encode("utf8"))
    content_disposition = f'attachment;filename="{filename}"'
    response.headers["content-disposition"] = content_disposition
    return response


@route("/attachments", methods=["POST"])
@csrf.protect
def attachment_upload() -> Response:
    title = request.args["title"].strip()
    try:
        page = get_page_by_title(title)
    except NoResultFound:
        raise NotFound()

    files = request.files.getlist("attachments")
    saved_count = 0

    for f in files:
        name = f.filename
        if not isinstance(name, str):
            name = str(f.filename, encoding="utf-8", errors="ignore")

        # FIXME: do something instead of just skipping the attachement
        if not name:
            continue

        attachment = WikiPageAttachment(name=name)
        attachment.wikipage = page
        attachment.set_content(f.read(), f.content_type)
        db.session.add(attachment)
        saved_count += 1

    if saved_count:
        db.session.commit()
        flash(
            _n(
                "One new document successfully uploaded",
                "%(num)d new documents successfully uploaded",
                count=saved_count,
                num=len(files),
            ),
            "success",
        )
    else:
        flash(_("No file uploaded."))

    return redirect(url_for(page))


@route("/attachments/delete", methods=["POST"])
@csrf.protect
def attachment_delete():
    title = request.args["title"].strip()
    attachment_id = int(request.args["attachment"])
    try:
        page = get_page_by_title(title)
    except NoResultFound:
        raise NotFound()

    attachment = WikiPageAttachment.query.get(attachment_id)
    assert attachment is not None
    assert attachment.wikipage is page

    if request.form.get("action") == "delete":
        name = attachment.name
        db.session.delete(attachment)
        db.session.commit()
        flash(_('Attachment "{name}" has been deleted').format(name=name))

    return redirect(url_for(page))


#
# Wiki-level (prefixed by 'wiki_')
#
@route("/pages")
def wiki_pages():
    pages = (
        WikiPage.query.filter(WikiPage.community_id == g.community.id)
        .order_by(WikiPage.title)
        .all()
    )
    return render_template("wiki/all_pages.html", pages=pages)


@route("/help")
def wiki_help():
    src = open(Path(__file__).parent / "data" / "help.txt").read()
    body = Markup(markdown(src))
    return render_template("wiki/help.html", body=body)


@route("/export")
def wiki_export():
    # TODO
    return "Not done yet"


#
# Util
#
def get_page_by_title(title: str) -> WikiPage:
    title = title.strip()
    page = WikiPage.query.filter(
        WikiPage.community_id == g.community.id, WikiPage.title == title
    ).one()
    return page


def create_home_page() -> WikiPage:
    path = Path(__file__).parent / "data" / "default_page.txt"
    default_src = path.open("rt").read()
    page = WikiPage(title="Home", body_src=default_src)
    page.community_id = g.community.id
    db.session.add(page)
    db.session.commit()
    return page
