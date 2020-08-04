"""Models for the Forum.

Note: a few features are planned but not implemented yet, and are commented
out.
"""
from collections import Counter
from datetime import datetime
from itertools import chain
from typing import Any

from sqlalchemy import Column, ForeignKey, Integer, Unicode, UnicodeText
from sqlalchemy.event import listens_for
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, relationship
from sqlalchemy.types import DateTime

from abilian.core.entities import SEARCHABLE, Entity
from abilian.sbe.apps.communities.models import Community, CommunityIdColumn, \
    community_content
from abilian.sbe.apps.documents.models import BaseContent
from abilian.services.indexing.adapter import SAAdapter


class ThreadClosedError(RuntimeError):
    def __init__(self, thread):
        super().__init__(
            "The thread {!r} is closed. No modification allowed on its posts: "
            "creation, edition, deletion".format(thread)
        )
        self.thread = thread


@community_content
class Thread(Entity):
    """A thread contains conversations among forum participants.

    The discussions in a thread may be sorted in chronological order or threaded
    by reply.

    (= Thread in SIOC, Message in ICOM 1.0).
    """

    __tablename__ = "forum_thread"

    community_id = CommunityIdColumn()
    #: The community this thread belongs to
    community = relationship(
        Community,
        primaryjoin=(community_id == Community.id),
        backref=backref("threads", cascade="all, delete-orphan"),
    )

    #: The thread title (aka subject)
    _title = Column("title", Unicode(255), nullable=False, default="", info=SEARCHABLE)

    last_post_at = Column(DateTime, default=datetime.utcnow, nullable=True)

    # title is defined has an hybrid property to allow name <-> title sync (2
    # way)
    @hybrid_property
    def title(self):
        return self._title

    def get_frequent_posters(self, limit):
        all_posts = self.posts[1:]
        posters_counter = Counter([e.creator for e in all_posts])
        sorted_posters = posters_counter.most_common(limit)
        frequent_posters = [
            user for (user, nb_posts) in sorted_posters if user != self.creator
        ]
        return frequent_posters

    @title.setter
    def title(self, title):
        # set title before setting name, so that we don't enter an infinite loop
        # with _thread_sync_name_title
        self._title = title
        if self.name != title:
            self.name = title

    posts = relationship(
        "Post",
        primaryjoin="Thread.id == Post.thread_id",
        order_by="Post.created_at",
        cascade="all, delete-orphan",
        back_populates="thread",
    )

    @property
    def closed(self):
        """True if this thread doesn't accept more posts."""
        return self.meta.get("abilian.sbe.forum", {}).get("closed", False)

    @closed.setter
    def closed(self, value):
        self.meta.setdefault("abilian.sbe.forum", {})["closed"] = bool(value)
        self.meta.changed()

    def create_post(self, **kw):
        if self.closed:
            raise ThreadClosedError(self)

        kw["name"] = self.name
        post = Post(**kw)
        post.thread = self
        return post


@listens_for(Thread.name, "set", active_history=True)
def _thread_sync_name_title(entity, new_value, old_value, initiator):
    """Synchronize thread name -> title.

    thread.title -> name is done via hybrid_property, avoiding infinite
    loop (since "set" is received before attribute has received value)
    """
    if entity.title != new_value:
        entity.title = new_value
    return new_value


class Post(Entity):
    """A post is a message in a forum discussion thread.

    (= Post in DiscussionMessage in ICOM 1.0).
    """

    __tablename__ = "forum_post"
    __indexable__ = False  # content is indexed at thread level

    #: The thread this post belongs to
    thread_id = Column(ForeignKey(Thread.id), nullable=False)
    thread = relationship(Thread, foreign_keys=thread_id, back_populates="posts")

    #: The post this post is a reply to, if any (currently not used)
    parent_post_id = Column(ForeignKey("forum_post.id"), nullable=True)
    parent_post = relationship("Post", foreign_keys=[parent_post_id])

    #: Markup type (Markdown, Textile...)
    # TODO: markup langage selection + default
    # markup_type = Column(String, default="Markdown")

    #: Source (markup) for the post
    # body_src = Column(UnicodeText, default=u"", nullable=False)

    #: HTML rendering of the post
    body_html = Column(UnicodeText, default="", nullable=False)

    @hybrid_property
    def title(self):
        return self.name

    @property
    def history(self):
        return self.meta.get("abilian.sbe.forum", {}).get("history", [])


class ThreadIndexAdapter(SAAdapter):
    """Index a thread and its posts."""

    @staticmethod
    def can_adapt(obj_cls: Any) -> bool:
        return obj_cls is Thread

    def get_document(self, obj):
        kw = super().get_document(obj)
        kw["text"] = " ".join(chain((kw["text"],), [p.body_html for p in obj.posts]))
        return kw


# event listener to sync name with thread's name
@listens_for(Thread.name, "set", active_history=True)
def _thread_sync_name(thread, new_value, old_value, initiator):
    """Synchronize name with thread's name."""
    if new_value == old_value:
        return new_value

    for post in thread.posts:
        post.name = new_value
    return new_value


@listens_for(Post.thread, "set", active_history=True)
def _thread_change_sync_name(post, new_thread, old_thread, initiator):
    """Change name on thread change."""
    if new_thread == old_thread or new_thread is None:
        return new_thread
    post.name = new_thread.name
    return new_thread


@listens_for(Thread.posts, "append")
@listens_for(Thread.posts, "remove")
@listens_for(Thread.posts, "set")
def _guard_closed_thread_collection(thread, value, *args):
    """Prevent add/remove/replace posts on a closed thread."""
    if isinstance(thread, Post):
        thread = thread.thread
        if thread is None:
            return

    if thread.closed:
        raise ThreadClosedError(thread)

    return value


class PostAttachment(BaseContent):
    __tablename__: str = None
    __mapper_args__ = {"polymorphic_identity": "forum_post_attachment"}
    sbe_type = "forum_post:attachment"

    _post_id = Column(Integer, ForeignKey(Post.id), nullable=True)
    post = relationship(
        Post,
        primaryjoin=(_post_id == Post.id),
        backref=backref(
            "attachments",
            lazy="select",
            order_by="PostAttachment.name",
            cascade="all, delete-orphan",
        ),
    )
