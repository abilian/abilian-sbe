# Copyright (c) 2012-2024, Abilian SAS

"""Forum views."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from itertools import groupby
from typing import TYPE_CHECKING, cast
from urllib.parse import quote

from flask import current_app, flash, g, make_response, render_template, request
from flask_babel import format_date
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from abilian.core.extensions.login import authenticated, authenticated_user
from abilian.core.sqlalchemy.session import session_of
from abilian.core.util import utc_dt
from abilian.i18n import _, _l
from abilian.sbe.apps.calendar.models import Event
from abilian.sbe.apps.communities import decorators as guard
from abilian.sbe.apps.communities.blueprint import (
    CommunityBlueprint,
    in_community,
    with_tool,
)
from abilian.sbe.apps.communities.common import activity_time_format, object_viewers
from abilian.sbe.apps.communities.security import can_manage
from abilian.sbe.apps.communities.views import default_view_kw
from abilian.sbe.apps.forum.security import can_write
from abilian.services.viewtracker import viewtracker
from abilian.web import url_for, views
from abilian.web.action import ButtonAction, Endpoint
from abilian.web.nav import BreadcrumbItem
from abilian.web.views import default_view

from .forms import PostEditForm, PostForm, ThreadForm
from .models import Post, PostAttachment, Thread
from .tasks import send_post_by_email

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from abilian.core.models.subjects import User

# TODO: move to config
MAX_THREADS = 30

forum = CommunityBlueprint(
    "forum", __name__, url_prefix="/forum", template_folder="templates"
)
route = forum.route
forum.before_request(in_community("thread_id", Thread))
forum.before_request(with_tool("has_forum"))


def post_kw_view_func(kw, obj, obj_type, obj_id, **kwargs):
    """kwargs for Post default view."""
    kw = default_view_kw(kw, obj.thread, obj_type, obj_id, **kwargs)
    kw["thread_id"] = obj.thread_id
    kw["_anchor"] = f"post_{obj.id:d}"
    return kw


@forum.url_value_preprocessor
def init_forum_values(endpoint, values) -> None:
    g.current_tab = "forum"

    g.breadcrumb.append(
        BreadcrumbItem(
            label=_l("Discussions"),
            url=Endpoint("forum.index", community_id=g.community.slug),
        )
    )


def get_viewed_posts(user: User, entities):
    if not entities:
        return None

    views = viewtracker.get_views(entities=entities, user=user)
    all_hits = viewtracker.get_hits(views=views)
    nb_viewed_posts = {}
    for view in views:
        related_hits = [hit for hit in all_hits if hit.view_id == view.id]
        entity = view.entity
        if entity in entities:
            cutoff = related_hits[-1].viewed_at
            nb_viewed_posts[entity] = len(
                [post for post in entity.posts if post.created_at > cutoff]
            )

    # A thread never opened is new from its first message on.
    never_viewed = set(entities) - {view.entity for view in views}
    for entity in never_viewed:
        nb_viewed_posts[entity] = len(entity.posts)

    return nb_viewed_posts


def get_viewed_times(entities):
    if entities:
        views = viewtracker.get_views(entities=entities)
        views = [
            view
            for view in views
            if view.user != view.entity.creator and view.user in g.community.members
        ]

        all_hits = viewtracker.get_hits(views=views)
        views_id = [view.view_id for view in all_hits]

        viewed_times = Counter(views_id)
        entity_viewed_times = {}
        for view in views:
            if view.entity not in entity_viewed_times:
                entity_viewed_times[view.entity] = viewed_times[view.id]
            else:
                entity_viewed_times[view.entity] += viewed_times[view.id]

        return entity_viewed_times
    return None


#: The "most read" filters: how far back each looks.
PERIODS = {
    "today": timedelta(days=1),
    "week": timedelta(days=7),
    "month": timedelta(days=31),
    "year": timedelta(days=365),
}


@route("/")
@route("/<string:filter>")
@authenticated
def index(user: User, filter=None):
    """A community's discussions, the latest active first; or, with a period, the
    most read started in it. `q` narrows them to those whose title has the words."""
    if filter and filter not in PERIODS:
        raise BadRequest
    q = request.args.get("q", "").strip()
    query = Thread.query.filter(Thread.community_id == g.community.id)
    if q:
        query = query.filter(Thread.title.ilike(f"%{q}%"))

    if filter:
        cutoff = datetime.utcnow() - PERIODS[filter]
        recent = query.filter(Thread.created_at > cutoff).all()
        views = get_viewed_times(recent) or {}
        threads = sorted(recent, key=lambda thread: -views.get(thread, 0))
        has_more = False
    else:
        query = query.order_by(Thread.last_post_at.desc())
        has_more = query.count() > MAX_THREADS
        threads = query.limit(MAX_THREADS).all()

    return render_template(
        "forum/index.html",
        threads=threads,
        has_more=has_more,
        unread=get_viewed_posts(user, threads) or {},
        filter=filter,
        q=q,
    )


def group_monthly[T](
    items: Iterable[T], when: Callable[[T], date]
) -> list[tuple[str, list[T]]]:
    """`items`, in their order, grouped by the month `when` says they are of, each
    group named after its month ("March 2026")."""

    # Python's groupby rather than SQL's GROUP BY: the same on SQLite and Postgres.
    def month(item: T) -> tuple[int, int]:
        return when(item).year, when(item).month

    def format_month(year: int, month: int) -> str:
        name = format_date(date(year, month, 1), "MMMM").capitalize()
        return f"{name} {year}"

    return [
        (format_month(year, month), list(group))
        for (year, month), group in groupby(items, month)
    ]


def created_at(entity: Thread | Post) -> date:
    """When `entity` was created: what the archives group by."""
    # Set on insert by the column's default; the model types it as nullable.
    return cast("date", entity.created_at)


@route("/archives/")
def archives():
    all_threads = (
        Thread.query.filter(Thread.community_id == g.community.id)
        .order_by(Thread.created_at.desc())
        .all()
    )

    grouped_threads = group_monthly(all_threads, created_at)
    return render_template("forum/archives.html", grouped_threads=grouped_threads)


@route("/attachments/")
def attachments():
    all_threads = (
        Thread.query.filter(Thread.community_id == g.community.id)
        .options(joinedload(Thread.posts).joinedload(Post.attachments))
        .order_by(Thread.created_at.desc())
        .all()
    )

    posts_with_attachments = []
    for thread in all_threads:
        for post in thread.posts:
            if getattr(post, "attachments", None):
                posts_with_attachments.append(post)
    posts_with_attachments.sort(key=lambda post: post.created_at)
    posts_with_attachments.reverse()

    grouped_posts = group_monthly(posts_with_attachments, created_at)
    return render_template("forum/attachments.html", grouped_posts=grouped_posts)


class BaseThreadView:
    Model: type[Thread | Post] = Thread
    pk = "thread_id"

    #: the logged-in user, set by `prepare_args()`
    user: User

    def can_send_by_mail(self):
        return g.community.type == "participative" or can_manage(self.user, g.community)

    def prepare_args(self, args, kwargs):
        # Before the parent's: it loads the object, which may need the user.
        self.user = authenticated_user()
        args, kwargs = super().prepare_args(args, kwargs)
        self.send_by_email = False

        if not self.can_send_by_mail() and "send_by_email" in self.form:
            # remove from html form and avoid validation errors
            del self.form["send_by_email"]

        return args, kwargs

    def index_url(self):
        return url_for(".index", community_id=g.community.slug)

    def view_url(self):
        return url_for(self.obj)


class ThreadView(BaseThreadView, views.ObjectView[Thread, PostForm]):
    methods = ["GET", "HEAD"]
    Form = PostForm
    template = "forum/thread.html"

    @property
    def template_kwargs(self):
        kw = super().template_kwargs
        kw.update(thread_page_kwargs(self.user, self.obj))
        viewtracker.record_hit(entity=self.obj, user=self.user)
        # The view keeps the hit; the tracker only records it.
        session_of(self.obj).commit()
        return kw


def thread_page_kwargs(user: User, thread: Thread) -> dict:
    """What a thread's page shows around its reply form.

    The unread posts are counted before the visit is recorded, which marks them read.
    """
    return {
        "thread": thread,
        "is_closed": thread.closed,
        "viewers": object_viewers(user, thread),
        "views": get_viewed_times([thread]),
        "participants": {post.creator for post in thread.posts},
        "activity_time_format": activity_time_format,
        # On its page, what is new comes after its first message, the thread itself.
        "new_posts": min(
            (get_viewed_posts(user, [thread]) or {}).get(thread, 0),
            len(thread.posts) - 1,
        ),
    }


thread_view = ThreadView.as_view("thread")
default_view(forum, Post, None, kw_func=post_kw_view_func)(thread_view)
default_view(forum, Thread, "thread_id", kw_func=default_view_kw)(thread_view)

route("/<int:thread_id>/")(thread_view)


class ThreadCreate(BaseThreadView, views.ObjectCreate[Thread, ThreadForm]):
    Form = ThreadForm
    template = "forum/thread_create.html"
    POST_BUTTON = ButtonAction(
        "form", "create", btn_class="primary", title=_l("Post this message")
    )

    title = _("New conversation")

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)
        self.thread = self.obj
        self.about = event_to_discuss(request.values.get("event"))
        if self.about is not None and not self.thread.title:
            self.thread.title = self.about.title
        return args, kwargs

    @property
    def template_kwargs(self):
        kw = super().template_kwargs
        kw["about"] = self.about
        return kw

    def before_populate_obj(self) -> None:
        del self.form["attachments"]
        self.message_body = self.form.message.data
        del self.form["message"]

        if "send_by_email" in self.form:
            self.send_by_email = (
                self.can_send_by_mail() and self.form.send_by_email.data
            )
            del self.form["send_by_email"]

    def after_populate_obj(self) -> None:
        if self.thread.community is None:
            self.thread.community = g.community._model
        if self.about is not None:
            self.about.thread = self.thread

        self.new_post = self.thread.create_post(body_html=self.message_body)
        obj_meta = self.new_post.meta.setdefault("abilian.sbe.forum", {})
        obj_meta["origin"] = "web"
        obj_meta["send_by_email"] = self.send_by_email
        attach_uploads(self.user, self.new_post)

    def commit_success(self) -> None:
        if self.send_by_email:
            message = send_post_by_email.send(self.new_post.id)
            # task = send_post_by_email.delay(self.new_post.id)
            meta = self.new_post.meta.setdefault("abilian.sbe.forum", {})
            # note: message_id is of type str
            meta["send_post_by_email_task"] = message.message_id
            self.new_post.meta.changed()
            session = session_of(self.new_post)
            session.commit()

    @property
    def activity_target(self):
        return self.thread.community

    def get_form_buttons(self, *args, **kwargs):
        return [self.POST_BUTTON, views.object.CANCEL_BUTTON]


route("/new_thread/")(ThreadCreate.as_view("new_thread", view_endpoint=".thread"))


def event_to_discuss(value: str | None) -> Event | None:
    """The event of this community a new thread is about, while it has none."""
    if not value:
        return None
    try:
        event_id = int(value)
    except ValueError as e:
        msg = f"Not an event: {value!r}"
        raise BadRequest(msg) from e
    return Event.query.filter(
        Event.id == event_id,
        Event.community_id == g.community.id,
        Event.thread_id.is_(None),
    ).first()


class ThreadPostCreate(ThreadCreate):
    """Add a new post to a thread.

    A reply the server refuses comes back on the thread's page, its error under it.
    """

    methods = ["POST"]
    Form = PostForm
    Model = Post
    template = "forum/thread.html"

    @property
    def template_kwargs(self):
        kw = super().template_kwargs
        kw.update(thread_page_kwargs(self.user, self.thread))
        return kw

    def init_object(self, args, kwargs):
        # we DO want to skip ThreadCreate.init_object. hence super is not based on
        # ThreadPostCreate
        args, kwargs = super().init_object(args, kwargs)
        thread_id = kwargs.pop(self.pk, None)
        self.thread = Thread.query.get(thread_id)
        Thread.query.filter(Thread.id == thread_id).update(
            {Thread.last_post_at: datetime.utcnow()}
        )
        return args, kwargs

    def after_populate_obj(self) -> None:
        super().after_populate_obj()
        session = session_of(self.obj)
        session.expunge(self.obj)
        self.obj = self.new_post


route("/<int:thread_id>/")(
    ThreadPostCreate.as_view("thread_post", view_endpoint=".thread")
)


class ThreadDelete(BaseThreadView, views.ObjectDelete[Thread, ThreadForm]):
    """Moderation: the community's managers', as the thread's page offers it."""

    Form = ThreadForm
    methods = ["POST"]
    decorators = (*views.ObjectDelete.decorators, guard.can_manage)
    _message_success = _('Thread "{title}" deleted.')

    def message_success(self):
        return str(self._message_success).format(title=self.obj.title)


route("/<int:thread_id>/delete")(ThreadDelete.as_view("thread_delete"))


class ThreadCloseView(BaseThreadView, views.object.BaseObjectView[Thread]):
    """Close / Re-open a thread: moderation, the community's managers'."""

    methods = ["POST"]
    decorators = (*views.object.BaseObjectView.decorators, guard.can_manage)
    _VALID_ACTIONS = {"close", "reopen"}
    CLOSED_MSG = _l("The thread is now closed for edition and new contributions.")
    REOPENED_MSG = _l("The thread is now re-opened for edition and new contributions.")

    def prepare_args(self, args, kwargs):
        args, kwargs = super().prepare_args(args, kwargs)
        action = kwargs["action"] = request.form.get("action")
        if action not in self._VALID_ACTIONS:
            msg = f"Unknown action: {action!r}"
            raise BadRequest(msg)

        return args, kwargs

    def post(self, action=None):
        is_closed = action == "close"
        self.obj.closed = is_closed
        session_of(self.obj).commit()

        msg = self.CLOSED_MSG if is_closed else self.REOPENED_MSG
        flash(str(msg))
        return self.redirect(url_for(self.obj))


route("/<int:thread_id>/close")(ThreadCloseView.as_view("thread_close"))


class ThreadPostEdit(BaseThreadView, views.ObjectEdit[Post, PostEditForm]):
    Form = PostEditForm
    Model = Post
    pk = "object_id"
    template = "forum/post_edit.html"

    def can_send_by_mail(self) -> bool:
        # post edit: don't notify every time
        return False

    def init_object(self, args, kwargs):
        # we DO want to skip ThreadCreate.init_object. hence super is not based on
        # ThreadPostCreate
        args, kwargs = super().init_object(args, kwargs)
        thread_id = kwargs.pop("thread_id", None)
        if self.obj is None:
            raise NotFound
        self.thread = self.obj.thread
        # The post is looked up by its id alone: under another thread's URL, it is
        # not found.
        if thread_id != self.thread.id:
            raise NotFound

        # Nothing checked whose post this was. The community blueprint gates
        # the route to members, so any member could edit any other member's
        # post through a URL the template declines to show them.
        if not can_write(self.user, self.obj):
            raise Forbidden

        return args, kwargs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["message"] = self.obj.body_html
        return kwargs

    @property
    def template_kwargs(self):
        kw = super().template_kwargs
        kw["post"] = self.obj
        kw["thread"] = self.thread
        return kw

    def before_populate_obj(self) -> None:
        self.message_body = self.form.message.data
        del self.form["message"]
        self.reason = self.form.reason.data

        self.send_by_email = False
        if "send_by_email" in self.form:
            del self.form["send_by_email"]

        self.attachments_to_remove = self.form["attachments"].delete_files_index
        del self.form["attachments"]

    def after_populate_obj(self) -> None:
        session = session_of(self.obj)
        self.obj.body_html = self.message_body
        obj_meta = self.obj.meta.setdefault("abilian.sbe.forum", {})
        history = obj_meta.setdefault("history", [])
        history.append(
            {
                "user_id": self.user.id,
                "user": str(self.user),
                "date": utc_dt(datetime.utcnow()).isoformat(),
                "reason": self.form.reason.data,
            }
        )
        self.obj.meta["abilian.sbe.forum"] = obj_meta  # trigger change for SA

        # The page numbers the post's files from 0; any other index is none of them.
        attachments = self.obj.attachments
        indexes = {int(idx) for idx in self.attachments_to_remove if idx.isdecimal()}
        for idx in sorted(indexes):
            if 0 <= idx < len(attachments):
                session.delete(attachments[idx])

        attach_uploads(self.user, self.obj)


route("/<int:thread_id>/<int:object_id>/edit")(ThreadPostEdit.as_view("post_edit"))


def attach_uploads(user: User, post: Post) -> None:
    """Attach to `post` the files `user` uploaded for the form, as its
    `attachments` handles name them. A handle that names none is skipped."""
    uploads = current_app.extensions["uploads"]
    session = session_of(post)
    for handle in request.form.getlist("attachments"):
        fileobj = uploads.get_file(user, handle)
        if fileobj is None:
            continue

        meta = uploads.get_metadata(user, handle)
        name = meta.get("filename", handle)
        if not isinstance(name, str):
            name = str(name, encoding="utf-8", errors="ignore")
        if not name:
            continue

        attachment = PostAttachment(name=name, post=post)
        with fileobj.open("rb") as f:
            attachment.set_content(f.read(), meta.get("mimetype"))
        session.add(attachment)


def attachment_kw_view_func(kw, obj, obj_type, obj_id, **kwargs):
    post = obj.post
    kw = default_view_kw(kw, post.thread, obj_type, obj_id, **kwargs)
    kw["thread_id"] = post.thread_id
    kw["post_id"] = post.id
    return kw


@route("/<int:thread_id>/posts/<int:post_id>/attachment/<int:attachment_id>")
@default_view(forum, PostAttachment, "attachment_id", kw_func=attachment_kw_view_func)
def attachment_download(thread_id, post_id, attachment_id):
    thread = Thread.query.get(thread_id)
    post = Post.query.get(post_id)
    attachment = PostAttachment.query.get(attachment_id)

    if (
        not (thread and post and attachment)
        or post.thread is not thread
        or attachment.post is not post
    ):
        raise NotFound

    # Don't fail too hard when attachment is not available.
    try:
        content = attachment.content or ""
    except AttributeError:
        return ""

    response = make_response(content)
    response.headers["content-length"] = attachment.content_length
    response.headers["content-type"] = attachment.content_type
    filename = quote(attachment.name.encode("utf8"))
    content_disposition = f'attachment;filename="{filename}"'
    response.headers["content-disposition"] = content_disposition
    return response
