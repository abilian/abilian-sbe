# coding=utf-8
"""
"""
from __future__ import absolute_import
from datetime import date
from itertools import groupby, chain

from abilian.services.security import security
from flask import g, render_template, current_app
from abilian.web.action import actions
from flask.ext.babel import format_date
from sqlalchemy.orm import joinedload

from abilian.sbe.apps.documents.models import Document, Folder
from abilian.sbe.apps.forum.models import Thread
from abilian.sbe.apps.communities.blueprint import Blueprint
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
  community = g.community._model
  actions.context['object'] = community

  all_files = []
  if community.has_forum:
    all_files += get_attachments_from_forum(community)

  if community.has_documents:
    all_files += get_attachments_from_dms(community)

  all_files = sorted(all_files, key=lambda doc: doc.date)
  all_files = list(reversed(all_files))
  # TODO: batch
  if len(all_files) > 50:
    all_files = all_files[0:50]

  grouped_docs = group_monthly(all_files)

  return render_template("wall/files.html", grouped_docs=grouped_docs)


class Attachment(object):
  def __init__(self, url, doc, date):
    self.url = url
    self.doc = doc
    self.date = date


def get_attachments_from_forum(community):
  all_threads = Thread.query \
    .filter(Thread.community_id == community.id) \
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


# FIXME: significant performance issues here, needs to be refactored.
def get_folders(community):
  def get_subfolders(folders):
    folder_ids = [f.id for f in folders]
    result = set(Folder.query.filter(Folder._parent_id.in_(folder_ids)).all())
    return result

  root = community.folder
  folders = {root}
  folders_of_rank_n = folders
  while True:
    folders_of_rank_n = get_subfolders(folders_of_rank_n)
    filtered_folders_of_rank_n = security.filter_with_permission(
      g.user, "read", folders_of_rank_n, inherit=True)
    if len(filtered_folders_of_rank_n) == 0:
      break
    folders.update(filtered_folders_of_rank_n)
    folders_of_rank_n = filtered_folders_of_rank_n
  return folders


# FIXME: significant performance issues here, needs major refactoring
def get_attachments_from_dms(community):
  folders = get_folders(community)
  folder_ids = sorted([f.id for f in folders])

  documents = Document.query.filter(Document._parent_id.in_(folder_ids)).all()

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
