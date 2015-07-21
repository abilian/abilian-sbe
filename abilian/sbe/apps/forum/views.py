# coding=utf-8
"""
Forum views
"""
from __future__ import absolute_import

from datetime import date
from itertools import groupby
from urllib import quote

from flask import g, render_template, request, make_response, current_app
from flask_login import current_user
from flask_babel import format_date
from werkzeug.exceptions import NotFound
import sqlalchemy as sa
from abilian.i18n import _, _l
from abilian.web.action import ButtonAction
from abilian.web.views import default_view
from abilian.web import nav, url_for, views

from abilian.sbe.apps.communities.blueprint import Blueprint
from abilian.sbe.apps.communities.views import default_view_kw
from .forms import ThreadForm, CommentForm
from .models import Thread, Post, PostAttachment
from .tasks import send_post_by_email



# TODO: move to config
MAX_THREADS = 30

forum = Blueprint("forum", __name__,
                  url_prefix="/forum",
                  template_folder="templates")
route = forum.route

def post_kw_view_func(kw, obj, obj_type, obj_id, **kwargs):
  """
  kwargs for Post default view
  """
  kw = default_view_kw(kw, obj.thread, obj_type, obj_id, **kwargs)
  kw['thread_id'] = obj.thread_id
  kw['_anchor'] = u'post_{:d}'.format(obj.id)
  return kw


@forum.url_value_preprocessor
def init_forum_values(endpoint, values):
  g.current_tab = 'forum'

  g.breadcrumb.append(
    nav.BreadcrumbItem(label=_(u'Conversations'),
                       url=nav.Endpoint('forum.index',
                                        community_id=g.community.slug)))


@route('/')
def index():
  query = Thread.query \
    .filter(Thread.community_id == g.community.id) \
    .order_by(Thread.created_at.desc())
  has_more = query.count() > MAX_THREADS
  threads = query.limit(MAX_THREADS).all()
  return render_template("forum/index.html",
                         threads=threads, has_more=has_more)


def group_monthly(entities_list):
  # We're using Python's groupby instead of SA's group_by here
  # because it's easier to support both SQLite and Postgres this way.
  def grouper(entity):
    return entity.created_at.year, entity.created_at.month

  def format_month(year, month):
    month = format_date(date(year, month, 1), "MMMM").capitalize()
    return u"%s %s" % (month, year)

  grouped_entities = groupby(entities_list, grouper)
  grouped_entities = [(format_month(year, month), list(entities))
                      for (year, month), entities in grouped_entities]
  return grouped_entities


@route('/archives/')
def archives():
  all_threads = Thread.query \
    .filter(Thread.community_id == g.community.id) \
    .order_by(Thread.created_at.desc()).all()

  grouped_threads = group_monthly(all_threads)
  return render_template('forum/archives.html',
                         grouped_threads=grouped_threads)


@route('/attachments/')
def attachments():
  all_threads = Thread.query \
    .filter(Thread.community_id == g.community.id) \
    .order_by(Thread.created_at.desc()).all()
  all_posts = []
  for thread in all_threads:
    for post in thread.posts:
      if hasattr(post, 'attachments'):
        all_posts.append(post)
  all_posts.sort(key=lambda entity: entity.created_at)
  all_posts.reverse()
  grouped_posts = group_monthly(all_posts)
  return render_template('forum/attachments.html',
                         grouped_posts=grouped_posts)


class BaseThreadView(object):
  Model = Thread
  Form = ThreadForm
  pk = 'thread_id'
  base_template = 'community/_base.html'

  def can_send_by_mail(self):
    return (g.community.type == 'participative'
            or g.community.has_permission(current_user, 'manage'))

  def prepare_args(self, args, kwargs):
    args, kwargs = super(BaseThreadView, self).prepare_args(args, kwargs)
    if not self.can_send_by_mail():
      del self.form['send_by_email']

    return args, kwargs

  def index_url(self):
    return url_for(".index", community_id=g.community.slug)

  def view_url(self):
    return url_for(self.obj)


class ThreadView(BaseThreadView, views.ObjectView):
  methods = ['GET', 'HEAD']
  Form = CommentForm
  template = 'forum/thread.html'

  @property
  def template_kwargs(self):
    kw = super(ThreadView, self).template_kwargs
    kw['thread'] = self.obj
    return kw


thread_view = ThreadView.as_view('thread')
default_view(forum, Post, None, kw_func=post_kw_view_func)(thread_view)
default_view(forum, Thread, 'thread_id', kw_func=default_view_kw)(thread_view)

route('/<int:thread_id>/')(thread_view)
route('/<int:thread_id>/attachments')(
  ThreadView.as_view('thread_attachments',
                     template='forum/thread_attachments.html')
)


class ThreadCreate(BaseThreadView, views.ObjectCreate):
  POST_BUTTON = ButtonAction('form', 'create', btn_class='primary',
                             title=_l(u'Post this message'))

  def init_object(self, args, kwargs):
    args, kwargs = super(ThreadCreate, self).init_object(args, kwargs)
    self.thread = self.obj
    return args, kwargs

  def before_populate_obj(self):
    del self.form['attachments']
    self.message_body = self.form.message.data
    del self.form['message']
    self.send_by_email = self.form.send_by_email.data and self.can_send_by_mail()
    del self.form['send_by_email']

  def after_populate_obj(self):
    if self.thread.community is None:
      self.thread.community = g.community._model

    self.post = self.thread.create_post(body_html=self.message_body)
    session = sa.orm.object_session(self.thread)
    uploads = current_app.extensions['uploads']

    for handle in request.form.getlist('attachments'):
      fileobj = uploads.get_file(current_user, handle)
      if fileobj is None:
        continue

      meta = uploads.get_metadata(current_user, handle)
      name = meta.get('filename', handle)
      mimetype = meta.get('mimetype', None)

      if not isinstance(name, unicode):
        name = unicode(name, encoding='utf-8', errors='ignore')

      if not name:
        continue

      attachment = PostAttachment(name=name)
      attachment.post = self.post

      with fileobj.open('rb') as f:
        attachment.set_content(f.read(), mimetype)
      session.add(attachment)

  def commit_success(self):
    if self.send_by_email:
      send_post_by_email.delay(self.post.id)

  @property
  def activity_target(self):
    return self.thread.community

  def get_form_buttons(self, *args, **kwargs):
    return [self.POST_BUTTON, views.object.CANCEL_BUTTON]


route('/new_thread/')(ThreadCreate.as_view('new_thread',
                                           view_endpoint='.thread'))


class ThreadPostCreate(ThreadCreate):
  methods = ['POST']
  Form = CommentForm
  Model = Post

  def init_object(self, args, kwargs):
    # we DO want to skip ThreadCreate.init_object. hence super is not based on
    # ThreadPostCreate
    args, kwargs = super(ThreadCreate, self).init_object(args, kwargs)
    thread_id = kwargs.pop(self.pk, None)
    self.thread = Thread.query.get(thread_id)
    return args, kwargs

  def after_populate_obj(self):
    super(ThreadPostCreate, self).after_populate_obj()
    session = sa.orm.object_session(self.obj)
    session.expunge(self.obj)
    self.obj = self.post


route('/<int:thread_id>/')(ThreadPostCreate.as_view('thread_post',
                                                    view_endpoint='.thread'))


class ThreadDelete(BaseThreadView, views.ObjectDelete):
  methods = ['POST']
  _message_success = _(u'Thread "{title}" deleted.')

  def message_success(self):
    return unicode(self._message_success).format(title=self.obj.title)


route('/<int:thread_id>/delete')(ThreadDelete.as_view('thread_delete'))


def attachment_kw_view_func(kw, obj, obj_type, obj_id, **kwargs):
  post = obj.post
  kw = default_view_kw(kw, post.thread, obj_type, obj_id, **kwargs)
  kw['thread_id'] = post.thread_id
  kw['post_id'] = post.id
  return kw


@route('/<int:thread_id>/posts/<int:post_id>/attachment/<int:attachment_id>')
@default_view(forum, PostAttachment, 'attachment_id',
              kw_func=attachment_kw_view_func)
def attachment_download(thread_id, post_id, attachment_id):
  thread = Thread.query.get(thread_id)
  post = Post.query.get(post_id)
  attachment = PostAttachment.query.get(attachment_id)

  if (not (thread and post and attachment)
      or post.thread is not thread
      or attachment.post is not post):
    raise NotFound()

  response = make_response(attachment.content)
  response.headers['content-length'] = attachment.content_length
  response.headers['content-type'] = attachment.content_type
  content_disposition = (
    'attachment;filename="{}"'.format(quote(attachment.name.encode('utf8')))
  )
  response.headers['content-disposition'] = content_disposition
  return response
