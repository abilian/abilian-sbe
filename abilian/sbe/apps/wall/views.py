# coding=utf-8
"""
"""
from __future__ import absolute_import
from datetime import date
from itertools import groupby

from abilian.sbe.apps.documents.models import Document

from abilian.sbe.apps.forum.models import Thread
from abilian.services.security import security, READ
from flask import g, render_template, current_app
from abilian.web.action import actions
from abilian.sbe.apps.communities.blueprint import Blueprint
from flask.ext.babel import format_date
from flask.ext.login import current_user

from sqlalchemy.orm import joinedload

from .util import get_recent_entries
from .presenters import ActivityEntryPresenter

wall = Blueprint("wall", __name__,
                 url_prefix="/wall",
                 template_folder="templates")
route = wall.route


@wall.url_value_preprocessor
def set_current_tab(endpoint, values):
  g.current_tab = 'wall'


@route('/')
def index():
  actions.context['object'] = g.community._model
  entries = get_recent_entries(20, community=g.community)
  entries = ActivityEntryPresenter.wrap_collection(entries)
  return render_template("wall/index.html", entries=entries)


@route('/files')
def files():
  actions.context['object'] = g.community._model

  files1 = get_attachments_from_forum()
  files2 = get_attachments_from_dms()
  files = files1 + files2
  files = sorted(files, key=lambda doc: doc.date)
  files = reversed(files)

  grouped_docs = group_monthly(files)

  return render_template("wall/files.html", grouped_docs=grouped_docs)


class Attachment(object):
  def __init__(self, url, doc, date):
    self.url = url
    self.doc = doc
    self.date = date


# Or use:
# from attr import attributes, attr
#
# @attributes
# class Attachment(object):
#   url = attr()
#   doc = attr()
#   #blob = attr()
#   date = attr()


def get_attachments_from_forum():
  all_threads = Thread.query \
    .filter(Thread.community_id == g.community.id) \
    .options(joinedload('posts')) \
    .options(joinedload('posts.attachments')) \
    .order_by(Thread.created_at.desc()).all()

  posts_with_attachments = []
  for thread in all_threads:
    for post in thread.posts:
      if getattr(post, 'attachments', None):
        posts_with_attachments.append(post)

  posts_with_attachments.sort(key=lambda post: post.created_at)
  posts_with_attachments.reverse()

  attachments = []
  for post in posts_with_attachments:
    for att in post.attachments:
      url = current_app.default_view.url_for(att)
      attachment = Attachment(url, att, att.created_at)
      attachments.append(attachment)

  return attachments


def get_attachments_from_dms():
  # FIXME: huge performance issues here, needs to be refactored.
  documents = Document.query.all()
  documents = [doc for doc in documents if doc.community == g.community]

  def is_visible(obj):
    return security.has_permission(current_user, READ, obj)

  documents = [doc for doc in documents if is_visible(doc)]

  attachments = []
  for doc in documents:
    url = current_app.default_view.url_for(doc)
    attachment = Attachment(url, doc, doc.created_at)
    attachments.append(attachment)

  return attachments


# FIXME: copy/pasted then hacked from forum/views.py
def group_monthly(objects):
  # We're using Python's groupby instead of SA's group_by here
  # because it's easier to support both SQLite and Postgres this way.
  def grouper(entity):
    return entity.date.year, entity.date.month

  def format_month(year, month):
    month = format_date(date(year, month, 1), "MMMM").capitalize()
    return u"%s %s" % (month, year)

  grouped = groupby(objects, grouper)
  grouped = [(format_month(year, month), list(objs))
             for (year, month), objs in grouped]
  return grouped
