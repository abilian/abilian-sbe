"""Forum views."""
from collections import Counter
from datetime import date, datetime, timedelta
from itertools import groupby
from urllib.parse import quote

import sqlalchemy as sa
from flask import current_app, flash, g, make_response, render_template, \
    request
from flask_babel import format_date
from flask_login import current_user
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import BadRequest, NotFound

from abilian.core.util import utc_dt
from abilian.i18n import _, _l
from abilian.sbe.apps.communities.security import is_manager
from abilian.services.viewtracker import viewtracker
from abilian.web import url_for, views
from abilian.web.action import ButtonAction, Endpoint
from abilian.web.nav import BreadcrumbItem
from abilian.web.views import default_view

from ..communities.blueprint import Blueprint
from ..communities.common import activity_time_format, object_viewers
from ..communities.views import default_view_kw
from .forms import PostEditForm, PostForm, ThreadForm
from .models import Post, PostAttachment, Thread
from .tasks import send_post_by_email

# TODO: move to config
MAX_THREADS = 30

forum = Blueprint("forum", __name__, url_prefix="/forum", template_folder="templates")
route = forum.route


def post_kw_view_func(kw, obj, obj_type, obj_id, **kwargs):
    """kwargs for Post default view."""
    kw = default_view_kw(kw, obj.thread, obj_type, obj_id, **kwargs)
    kw["thread_id"] = obj.thread_id
    kw["_anchor"] = f"post_{obj.id:d}"
    return kw


@forum.url_value_preprocessor
def init_forum_values(endpoint, values):
    g.current_tab = "forum"

    g.breadcrumb.append(
        BreadcrumbItem(
            label=_l("Conversations"),
            url=Endpoint("forum.index", community_id=g.community.slug),
        )
    )


def get_nb_viewers(entities):
    if entities:
        views = viewtracker.get_views(entities=entities)
        threads = [
            thread.entity
            for thread in views
            if thread.user in g.community.members
            and thread.user != thread.entity.creator
        ]

        return Counter(threads)


def get_viewed_posts(entities):
    if not entities:
        return

    views = viewtracker.get_views(entities=entities, user=current_user)
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

    never_viewed = set(entities) - {view.entity for view in views}
    for entity in never_viewed:
        nb_viewed_posts[entity] = len(entity.posts) - 1

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


@route("/")
@route("/<string:filter>")
def index(filter=None):
    query = Thread.query.filter(Thread.community_id == g.community.id).order_by(
        Thread.last_post_at.desc()
    )

    threads = query.all()
    has_more = False

    nb_viewed_times = get_viewed_times(threads)
    for thread in threads:
        thread.nb_views = nb_viewed_times.get(thread, 0)

    dt = None
    if filter == "today":
        dt = timedelta(days=1)
    elif filter == "week":
        dt = timedelta(days=7)
    elif filter == "month":
        dt = timedelta(days=31)
    elif filter == "year":
        dt = timedelta(days=365)
    elif filter:
        raise BadRequest()

    if dt:
        cutoff_date = datetime.utcnow() - dt
        threads = [thread for thread in threads if thread.created_at > cutoff_date]

    if dt:
        threads = sorted(threads, key=lambda thread: -thread.nb_views)
    else:
        has_more = query.count() > MAX_THREADS
        threads = query.limit(MAX_THREADS).all()

    nb_viewers = get_nb_viewers(threads)
    nb_viewed_posts = get_viewed_posts(threads)

    return render_template(
        "forum/index.html",
        threads=threads,
        has_more=has_more,
        nb_viewers=nb_viewers,
        nb_viewed_posts=nb_viewed_posts,
        nb_viewed_times=nb_viewed_times,
        activity_time_format=activity_time_format,
    )


def group_monthly(entities_list):
    # We're using Python's groupby instead of SA's group_by here
    # because it's easier to support both SQLite and Postgres this way.
    def grouper(entity):
        return entity.created_at.year, entity.created_at.month

    def format_month(year, month):
        month = format_date(date(year, month, 1), "MMMM").capitalize()
        return f"{month} {year}"

    grouped_entities = groupby(entities_list, grouper)
    grouped_entities = [
        (format_month(year, month), list(entities))
        for (year, month), entities in grouped_entities
    ]
    return grouped_entities


@route("/archives/")
def archives():
    all_threads = (
        Thread.query.filter(Thread.community_id == g.community.id)
        .order_by(Thread.created_at.desc())
        .all()
    )

    grouped_threads = group_monthly(all_threads)
    return render_template("forum/archives.html", grouped_threads=grouped_threads)


@route("/attachments/")
def attachments():
    all_threads = (
        Thread.query.filter(Thread.community_id == g.community.id)
        .options(joinedload("posts"))
        .options(joinedload("posts.attachments"))
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

    grouped_posts = group_monthly(posts_with_attachments)
    return render_template("forum/attachments.html", grouped_posts=grouped_posts)


class BaseThreadView:
    Model = Thread
    Form = ThreadForm
    pk = "thread_id"
    base_template = "community/_base.html"

    def can_send_by_mail(self):
        return g.community.type == "participative" or is_manager(user=current_user)

    def prepare_args(self, args, kwargs):
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


class ThreadView(BaseThreadView, views.ObjectView):
    methods = ["GET", "HEAD"]
    Form = PostForm
    template = "forum/thread.html"

    @property
    def template_kwargs(self):
        kw = super().template_kwargs
        kw["thread"] = self.obj
        kw["is_closed"] = self.obj.closed
        kw["is_manager"] = is_manager(user=current_user)
        kw["viewers"] = object_viewers(self.obj)
        kw["views"] = get_viewed_times([self.obj])
        kw["participants"] = {post.creator for post in self.obj.posts}
        kw["activity_time_format"] = activity_time_format
        viewtracker.record_hit(entity=self.obj, user=current_user)
        return kw


thread_view = ThreadView.as_view("thread")
default_view(forum, Post, None, kw_func=post_kw_view_func)(thread_view)
default_view(forum, Thread, "thread_id", kw_func=default_view_kw)(thread_view)

route("/<int:thread_id>/")(thread_view)
route("/<int:thread_id>/attachments")(
    ThreadView.as_view("thread_attachments", template="forum/thread_attachments.html")
)


class ThreadCreate(BaseThreadView, views.ObjectCreate):
    base_template = "community/_forumbase.html"
    template = "forum/thread_create.html"
    POST_BUTTON = ButtonAction(
        "form", "create", btn_class="primary", title=_l("Post this message")
    )

    title = _("New conversation")

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)
        self.thread = self.obj
        return args, kwargs

    def before_populate_obj(self):
        del self.form["attachments"]
        self.message_body = self.form.message.data
        del self.form["message"]

        if "send_by_email" in self.form:
            self.send_by_email = (
                self.can_send_by_mail() and self.form.send_by_email.data
            )
            del self.form["send_by_email"]

    def after_populate_obj(self):
        if self.thread.community is None:
            self.thread.community = g.community._model

        self.post = self.thread.create_post(body_html=self.message_body)
        obj_meta = self.post.meta.setdefault("abilian.sbe.forum", {})
        obj_meta["origin"] = "web"
        obj_meta["send_by_email"] = self.send_by_email
        session = sa.orm.object_session(self.thread)
        uploads = current_app.extensions["uploads"]

        for handle in request.form.getlist("attachments"):
            fileobj = uploads.get_file(current_user, handle)
            if fileobj is None:
                continue

            meta = uploads.get_metadata(current_user, handle)
            name = meta.get("filename", handle)
            mimetype = meta.get("mimetype")

            if not isinstance(name, str):
                name = str(name, encoding="utf-8", errors="ignore")

            if not name:
                continue

            attachment = PostAttachment(name=name)
            attachment.post = self.post

            with fileobj.open("rb") as f:
                attachment.set_content(f.read(), mimetype)
            session.add(attachment)

    def commit_success(self):
        if self.send_by_email:
            task = send_post_by_email.delay(self.post.id)
            meta = self.post.meta.setdefault("abilian.sbe.forum", {})
            meta["send_post_by_email_task"] = task.id
            self.post.meta.changed()
            session = sa.orm.object_session(self.post)
            session.commit()

    @property
    def activity_target(self):
        return self.thread.community

    def get_form_buttons(self, *args, **kwargs):
        return [self.POST_BUTTON, views.object.CANCEL_BUTTON]


route("/new_thread/")(ThreadCreate.as_view("new_thread", view_endpoint=".thread"))


class ThreadPostCreate(ThreadCreate):
    """Add a new post to a thread."""

    methods = ["POST"]
    Form = PostForm
    Model = Post

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

    def after_populate_obj(self):
        super().after_populate_obj()
        session = sa.orm.object_session(self.obj)
        session.expunge(self.obj)
        self.obj = self.post


class ThreadViewers(ThreadView):

    template = "forum/thread_viewers.html"


route("/<int:thread_id>/")(
    ThreadPostCreate.as_view("thread_post", view_endpoint=".thread")
)

route("/<int:thread_id>/viewers")(ThreadViewers.as_view("thread_viewers"))


class ThreadDelete(BaseThreadView, views.ObjectDelete):
    methods = ["POST"]
    _message_success = _('Thread "{title}" deleted.')

    def message_success(self):
        return str(self._message_success).format(title=self.obj.title)


route("/<int:thread_id>/delete")(ThreadDelete.as_view("thread_delete"))


class ThreadCloseView(BaseThreadView, views.object.BaseObjectView):
    """Close / Re-open a thread."""

    methods = ["POST"]
    _VALID_ACTIONS = {"close", "reopen"}
    CLOSED_MSG = _l("The thread is now closed for edition and new " "contributions.")
    REOPENED_MSG = _l(
        "The thread is now re-opened for edition and new " "contributions."
    )

    def prepare_args(self, args, kwargs):
        args, kwargs = super().prepare_args(args, kwargs)
        action = kwargs["action"] = request.form.get("action")
        if action not in self._VALID_ACTIONS:
            raise BadRequest(f"Unknown action: {action!r}")

        return args, kwargs

    def post(self, action=None):
        is_closed = action == "close"
        self.obj.closed = is_closed
        sa.orm.object_session(self.obj).commit()

        msg = self.CLOSED_MSG if is_closed else self.REOPENED_MSG
        flash(str(msg))
        return self.redirect(url_for(self.obj))


route("/<int:thread_id>/close")(ThreadCloseView.as_view("thread_close"))


class ThreadPostEdit(BaseThreadView, views.ObjectEdit):
    Form = PostEditForm
    Model = Post
    pk = "object_id"

    def can_send_by_mail(self):
        # post edit: don't notify every time
        return False

    def init_object(self, args, kwargs):
        # we DO want to skip ThreadCreate.init_object. hence super is not based on
        # ThreadPostCreate
        args, kwargs = super().init_object(args, kwargs)
        thread_id = kwargs.pop("thread_id", None)
        self.thread = self.obj.thread
        assert thread_id == self.thread.id
        return args, kwargs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["message"] = self.obj.body_html
        return kwargs

    def before_populate_obj(self):
        self.message_body = self.form.message.data
        del self.form["message"]
        self.reason = self.form.reason.data

        self.send_by_email = False
        if "send_by_email" in self.form:
            del self.form["send_by_email"]

        self.attachments_to_remove = self.form["attachments"].delete_files_index
        del self.form["attachments"]

    def after_populate_obj(self):
        session = sa.orm.object_session(self.obj)
        uploads = current_app.extensions["uploads"]
        self.obj.body_html = self.message_body
        obj_meta = self.obj.meta.setdefault("abilian.sbe.forum", {})
        history = obj_meta.setdefault("history", [])
        history.append(
            {
                "user_id": current_user.id,
                "user": str(current_user),
                "date": utc_dt(datetime.utcnow()).isoformat(),
                "reason": self.form.reason.data,
            }
        )
        self.obj.meta["abilian.sbe.forum"] = obj_meta  # trigger change for SA

        attachments_to_remove = []
        for idx in self.attachments_to_remove:
            try:
                idx = int(idx)
            except ValueError:
                continue

            if idx > len(self.obj.attachments):
                continue

            attachments_to_remove.append(self.obj.attachments[idx])

        for att in attachments_to_remove:
            session.delete(att)

        for handle in request.form.getlist("attachments"):
            fileobj = uploads.get_file(current_user, handle)
            if fileobj is None:
                continue

            meta = uploads.get_metadata(current_user, handle)
            name = meta.get("filename", handle)
            mimetype = meta.get("mimetype")

            if not isinstance(name, str):
                name = str(name, encoding="utf-8", errors="ignore")

            if not name:
                continue

            attachment = PostAttachment(name=name, post=self.obj)

            with fileobj.open("rb") as f:
                attachment.set_content(f.read(), mimetype)
            session.add(attachment)


route("/<int:thread_id>/<int:object_id>/edit")(ThreadPostEdit.as_view("post_edit"))


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
        raise NotFound()

    response = make_response(attachment.content)
    response.headers["content-length"] = attachment.content_length
    response.headers["content-type"] = attachment.content_type
    filename = quote(attachment.name.encode("utf8"))
    content_disposition = f'attachment;filename="{filename}"'
    response.headers["content-disposition"] = content_disposition
    return response
