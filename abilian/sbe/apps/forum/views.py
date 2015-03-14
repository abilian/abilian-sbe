from datetime import date
from itertools import groupby
from urllib import quote

from flask import g, render_template, redirect, request, \
    current_app, abort, flash, make_response
from flask.ext.babel import format_date, gettext as _
from flask.ext.login import current_user

from abilian.core.signals import activity
from abilian.core.extensions import db
from abilian.web.action import actions
from abilian.web.views import default_view
from abilian.web import nav, url_for

from abilian.sbe.apps.communities.blueprint import Blueprint
from abilian.sbe.apps.communities.views import default_view_kw
from abilian.sbe.apps.communities.security import require_access

from .forms import ThreadForm, CommentForm
from .models import Thread, Post, PostAttachment
from .tasks import send_post_by_email


# TODO: move to config
MAX_THREADS = 30

forum = Blueprint("forum", __name__,
                  url_prefix="/forum",
                  template_folder="templates")
route = forum.route


@forum.url_value_preprocessor
def init_forum_values(endpoint, values):
  g.current_tab = 'forum'

  g.breadcrumb.append(
    nav.BreadcrumbItem(label=_(u'Conversations'),
                       url=nav.Endpoint('forum.index',
                                        community_id=g.community.slug)))


@route('/')
@require_access
def index():
  query = Thread.query\
    .filter(Thread.community_id == g.community.id)\
    .order_by(Thread.created_at.desc())
  has_more = query.count() > MAX_THREADS
  threads = query.limit(MAX_THREADS).all()
  return render_template("forum/index.html",
                         threads=threads, has_more=has_more)


@route('/archives/')
@require_access
def archives():
  # We're using Python's groupby instead of SA's group_by here
  # because it's easier to support both SQLite and Postgres this way.

  all_threads = Thread.query \
    .filter(Thread.community_id == g.community.id) \
    .order_by(Thread.created_at.desc()).all()

  def grouper(thread):
    return thread.created_at.year, thread.created_at.month

  def format_month(year, month):
    month = format_date(date(year, month, 1), "MMMM").capitalize()
    return u"%s %s" % (month, year)

  grouped_threads = groupby(all_threads, grouper)
  grouped_threads = [(format_month(year, month), list(threads))
                     for (year, month), threads in grouped_threads]
  return render_template("forum/archives.html",
                         grouped_threads=grouped_threads)


@route('/new_thread/')
@require_access
def new_thread():
  form = ThreadForm()
  return render_template("forum/new_thread.html", form=form)


@route('/new_thread/', methods=['POST'])
@require_access
def new_thread_post():
  action = request.form.get('_action')
  if action != 'post':
    return redirect(url_for(".index", community_id=g.community.slug))

  form = ThreadForm(request.form)

  if form.validate():
    thread = create_thread(form.title.data, form.message.data,
                           request.files.getlist('attachments'))
    db.session.commit()
    if form.send_by_email.data and \
        (g.community.type == 'participative' or g.community.has_permission(current_user, 'manage')):
      post = thread.posts[0]
      send_post_by_email.delay(post.id)
    return redirect(url_for(thread))
  else:
    flash(_(u"Please fix the errors below"), "error")
    return render_template('forum/new_thread.html', form=form)


def post_kw_view_func(kw, obj, obj_type, obj_id, **kwargs):
  kw = default_view_kw(kw, obj.thread, obj_type, obj_id, **kwargs)
  kw['thread_id'] = obj.thread_id
  kw['_anchor'] = u'post_{:d}'.format(obj.id)
  return kw


@route('/<int:thread_id>/')
@default_view(forum, Thread, 'thread_id', kw_func=default_view_kw)
@default_view(forum, Post, None, kw_func=post_kw_view_func)
@require_access
def thread(thread_id):
  thread = Thread.query.get(thread_id)
  actions.context['object'] = thread

  if not thread:
    abort(404)
  form = CommentForm()
  return render_template('forum/thread.html', thread=thread, form=form)


@route('/<int:thread_id>/', methods=['POST'])
@require_access
def thread_post(thread_id):
  thread = Thread.query.get(thread_id)
  if not thread:
    abort(404)

  action = request.form.get('_action')
  if action != 'post':
    return redirect(url_for(thread))

  form = CommentForm(request.form)
  if form.validate():
    post = thread.create_post(body_html=form.message.data)
    create_post_attachments(post, request.files.getlist('attachments'))

    # Send signal
    app = current_app._get_current_object()
    community = g.community._model
    activity.send(app, actor=g.user, verb="post", object=post, target=community)

    db.session.commit()
    if form.send_by_email.data and \
        (g.community.type == 'participative'
         or g.community.has_permission(current_user, 'manage')):
      send_post_by_email.delay(post.id)

    return redirect(url_for(thread))

  else:
    flash(_(u"Please fix the errors below"), "error")
    return render_template('forum/thread.html', thread=thread, form=form)


@route('/<int:thread_id>/delete', methods=['POST'])
def thread_delete(thread_id):
  thread = Thread.query.get(thread_id)
  if not thread:
    abort(404)

  posts = thread.posts
  # FIXME: should be taken care of by the cascade but that doesn't work.
  for post in posts:
    db.session.delete(post)
  db.session.delete(thread)

  app = current_app._get_current_object()
  community = g.community._model
  activity.send(app, actor=g.user, verb="delete", object=thread, target=community)

  db.session.commit()
  flash(_(u"Thread {title} deleted.".format(title=thread.title)))
  return redirect(url_for(".index", community_id=g.community.slug))


def attachment_kw_view_func(kw, obj, obj_type, obj_id, **kwargs):
  post = obj.post
  kw = default_view_kw(kw, post.thread, obj_type, obj_id, **kwargs)
  kw['thread_id'] = post.thread_id
  kw['post_id'] = post.id
  return kw


@route('/<int:thread_id>/posts/<int:post_id>/attachment/<int:attachment_id>')
@default_view(forum, PostAttachment, 'attachment_id',
              kw_func=attachment_kw_view_func)
@require_access
def attachment_download(thread_id, post_id, attachment_id):
  thread = Thread.query.get(thread_id)
  post = Post.query.get(post_id)
  attachment = PostAttachment.query.get(attachment_id)

  if (not (thread and post and attachment)
      or post.thread is not thread
      or attachment.post is not post):
    abort(404)

  response = make_response(attachment.content)
  response.headers['content-length'] = attachment.content_length
  response.headers['content-type'] = attachment.content_type
  content_disposition = (
    'attachment;filename="{}"'.format(quote(attachment.name.encode('utf8')))
  )
  response.headers['content-disposition'] = content_disposition
  return response


def create_thread(title, message, files=()):
  thread = Thread(title=title, community=g.community)
  post = Post(thread=thread, body_html=message)
  create_post_attachments(post, files)
  db.session.add(thread)

  # Send signal
  app = current_app._get_current_object()
  community = g.community._model
  activity.send(app, actor=g.user, verb="post", object=thread, target=community)

  return thread


def create_post_attachments(post, files):
  for f in files:
    name = f.filename
    if not isinstance(name, unicode):
      name = unicode(f.filename, encoding='utf-8', errors='ignore')

    if not name:
      continue

    attachment = PostAttachment(name=name)
    attachment.post = post
    attachment.set_content(f.read(), f.content_type)
    db.session.add(attachment)
