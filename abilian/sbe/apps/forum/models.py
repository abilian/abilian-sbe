# coding=utf-8
"""
Models for the Forum.

Note: a few features are planned but not implemented yet, and are commented
out.
"""
from __future__ import absolute_import
from itertools import chain

import sqlalchemy as sa
from sqlalchemy import Column, Integer, ForeignKey, Unicode, UnicodeText
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.hybrid import hybrid_property

from abilian.core.entities import Entity, SEARCHABLE
from abilian.services.indexing.adapter import SAAdapter

from abilian.sbe.apps.communities.models import (
  Community, CommunityIdColumn, community_content,
  )
from abilian.sbe.apps.documents.models import BaseContent, CmisObject


@community_content
class Thread(Entity):
  """
  A thread contains conversations among forum participants.
  The discussions in a thread may be sorted in chronological order or threaded by reply.

  (= Thread in SIOC, Message in ICOM 1.0).
  """
  __tablename__ = 'forum_thread'

  community_id = CommunityIdColumn()
  #: The community this thread belongs to
  community = relationship(Community,
                           primaryjoin=(community_id == Community.id),
                           backref=backref('threads',
                                           cascade="all, delete-orphan"))

  #: The thread title (aka subject)
  _title = Column('title', Unicode(255), nullable=False,
                  default=u"", info=SEARCHABLE)

  #: The number of posts in the thread
  #post_count = Column(Integer, nullable=False, default=0)

  #: The number of time the thread has been viewed
  #view_count = Column(Integer, nullable=False, default=0)

  #: Is the thread sticky? [Not used]
  #sticky = Column(Integer, nullable=False, default=False)

  #: Is it open or closed?
  #closed = Column(Integer, nullable=False, default=False)

  #: List of subscribers (users who receive email alerts on updates)
  # TODO

  # TODO
  #last_post_id = Column(ForeignKey(lambda : Post.id), nullable=True)
  #last_post = relationship(lambda : Post)

  # title is defined has an hybrid property to allow name <-> title sync (2 way)
  @hybrid_property
  def title(self):
    return self._title

  @title.setter
  def title(self, title):
    # set title before setting name, so that we don't enter an infinite loop
    # with _thread_sync_name_title
    self._title = title
    if self.name != title:
      self.name = title

  def create_post(self, **kw):
    kw['name'] = self.name
    post = Post(**kw)
    post.thread = self
    return post


@sa.event.listens_for(Thread.name, "set", active_history=True)
def _thread_sync_name_title(entity, new_value, old_value, initiator):
  """
  Synchronize thread name -> title.
  thread.title -> name is done via hybrid_property, avoiding infinite
  loop (since "set" is received before attribute has received value)
  """
  if entity.title != new_value:
    entity.title = new_value
  return new_value


class Post(Entity):
  """
  A post is a message in a forum discussion thread.

  (= Post in DiscussionMessage in ICOM 1.0).
  """
  __tablename__ = 'forum_post'
  __indexable__ = False # content is indexed at thread level

  #: The thread this post belongs to
  thread_id = Column(ForeignKey(Thread.id), nullable=False)
  thread = relationship(Thread,
                        foreign_keys=[thread_id],
                        backref=backref('posts',
                                        order_by='Post.created_at',
                                        cascade="all, delete-orphan"))

  #: The post this post is a reply to, if any (currently not used)
  parent_post_id = Column(ForeignKey("forum_post.id"), nullable=True)
  parent_post = relationship("Post", foreign_keys=[parent_post_id])

  #: Markup type (Markdown, Textile...)
  # TODO: markup langage selection + default
  #markup_type = Column(String, default="Markdown")

  #: Source (markup) for the post
  #body_src = Column(UnicodeText, default=u"", nullable=False)

  #: HTML rendering of the post
  body_html = Column(UnicodeText, default=u"", nullable=False)

  @hybrid_property
  def title(self):
    return self.name


class ThreadIndexAdapter(SAAdapter):
  """
  Index a thread and its posts
  """
  @staticmethod
  def can_adapt(obj_cls):
    return obj_cls is Thread

  def get_document(self, obj):
    kw = super(ThreadIndexAdapter, self).get_document(obj)
    kw['text'] = u' '.join(chain((kw['text'],), [p.body_html for p in obj.posts]))
    return kw


# event listener to sync name with thread's name
@sa.event.listens_for(Thread.name, "set", active_history=True)
def _thread_sync_name(thread, new_value, old_value, initiator):
  """
  Synchronize name with thread's name.
  """
  if new_value == old_value:
    return new_value

  for post in thread.posts:
    post.name = new_value
  return new_value

@sa.event.listens_for(Post.thread, "set", active_history=True)
def _thread_change_sync_name(post, new_thread, old_thread, initiator):
  """
  Change name on thread change
  """
  if new_thread == old_thread:
    return new_thread
  post.name = new_thread.name
  return new_thread


class PostAttachment(BaseContent, CmisObject):
  __tablename__ = None
  __mapper_args__ = {'polymorphic_identity': 'forum_post_attachment'}
  sbe_type = 'forum_post:attachment'

  _post_id = Column(Integer, ForeignKey(Post.id), nullable=True)
  post = relationship(Post,
                      primaryjoin=(_post_id == Post.id),
                      backref=backref('attachments', lazy='select',
                                      order_by='PostAttachment.name',
                                      cascade='all, delete-orphan'))

# class Vote(db.Model):
#   id = Column(Integer, primary_key=True, info=SYSTEM)
#
#   #: Who voted
#   voter_id = Column(ForeignKey(User.id))
#
#   #:
#   voter = relationship(User)
#
#   #: On which post
#   post_id = Column(ForeignKey(Post.id))
#
#   #:
#   post = relationship(Post, backref='voters')
#
#   #: The vote value, usually 0, +1 or -1
#   value = Column(Integer, nullable=False)
