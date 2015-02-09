# coding=utf-8
"""
"""
from __future__ import absolute_import

import hashlib
from functools import wraps
from pathlib import Path

from whoosh.searching import Hit

from werkzeug.exceptions import NotFound, BadRequest
from flask import (
    render_template, g, redirect, url_for, abort,
    request, current_app, session,
)
from flask.ext.login import current_user

from abilian.core.extensions import db
from abilian.core.signals import activity
from abilian.core.models.subjects import User
from abilian.web import csrf, nav, views
from abilian.web.views import images as image_views
from abilian.i18n import _, _l

from abilian.sbe.apps.documents.models import Document

from .actions import register_actions
from .forms import CommunityForm
from .models import Community, Membership
from .security import require_admin, require_manage
from .blueprint import Blueprint

__all__ = ['communities']

communities = Blueprint("communities", __name__,
                        set_community_id_prefix=False,
                        template_folder='templates')
route = communities.route
add_url = communities.add_url_rule
communities.record_once(register_actions)

@communities.record_once
def register_context_processors(state):
  @state.app.context_processor
  def communities_context_processor():
    # helper to get an url for community image
    return dict(community_image_url=image_url)


def tab(tab_name):
  """
  Decorator for view functions to set the current "section" this view
  belongs to.
  """
  def decorator(f):
    @wraps(f)
    def set_current_tab(*args, **kwargs):
      g.current_tab = tab_name
      return f(*args, **kwargs)

    return set_current_tab
  return decorator


def default_view_kw(kw, obj, obj_type, obj_id, **kwargs):
  """
  Helper for using :func:`abilian.web.views.default_view` on objects that
  belongs to a community. This function should be used as `kw_func`::

      @default_view(blueprint, Model, kw_func=default_view_kw)
      @blueprint.route("/<object_id>")
      def view():
         ...

  """
  is_community = obj_type == Community.entity_type
  community_id = kw.get('community_id')

  if is_community or community_id is None:
    # when it's a community, default_view sets community_id to 'id', we want to
    # override with the slug value.
    if obj:
      if isinstance(obj, (Hit, dict)):
        community_id = obj.get('slug' if is_community else 'community_slug')
      elif is_community:
        community_id = obj.slug
      elif community_id is None and hasattr(obj, 'community'):
        try:
          community_id = obj.community.slug
        except AttributeError:
          pass

  if community_id is not None:
    kw['community_id'] = community_id
  else:
    raise ValueError('Cannot find community_id value')

  return kw


#
# Routes
#
@route("/")
def index():
  query = Community.query
  sort_order = request.args.get('sort', u'').strip()
  if not sort_order:
    sort_order = session.get('sort_communities_order', 'alpha')

  if sort_order == 'activity':
    query = query.order_by(Community.last_active_at.desc())
  else:
    query = query.order_by(Community.name)

  session['sort_communities_order'] = sort_order

  if not current_user.has_role('admin'):
    # Filter with permissions
    query = query.join(Membership).filter(Membership.user == current_user)

  ctx = dict(my_communities=query.all(), sort_order=sort_order)
  return render_template("community/home.html", **ctx)


@route("/<string:community_id>/")
@views.default_view(communities, Community, 'community_id',
                    kw_func=default_view_kw)
def community():
  return redirect(url_for("wall.index", community_id=g.community.slug))


# edit views
class BaseCommunityView(object):
  Model = Community
  pk = 'community_id'
  Form = CommunityForm
  base_template = 'community/_base.html'
  decorators = [require_admin]

  def init_object(self, args, kwargs):
    self.obj = g.community._model
    return args, kwargs

  def view_url(self):
    return url_for(self.view_endpoint, community_id=self.obj.slug)

  def get_form_kwargs(self):
    image = self.obj.image
    kwargs = dict()
    if image and 'community' in g:
      setattr(image, 'url', image_url(g.community))
      kwargs['image'] = image

    return kwargs


class CommunityEdit(BaseCommunityView, views.ObjectEdit):
  template = 'community/edit.html'
  title = _l("Edit community")
  decorators = [require_admin, tab('settings')]

  def breadcrumb(self):
    return nav.BreadcrumbItem(label=_(u'Settings'),
                              icon='cog',
                              url=nav.Endpoint('communities.settings',
                                               community_id=g.community.slug))

  def get_form_kwargs(self):
    kwargs = views.ObjectEdit.get_form_kwargs(self)
    kwargs.update(BaseCommunityView.get_form_kwargs(self))
    return kwargs

  def before_populate_obj(self):
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


add_url("/<string:community_id>/settings",
        view_func=CommunityEdit.as_view(
          'settings',
          view_endpoint='.community',
          message_success=_l(u"Community settings saved successfully.")))


class CommunityCreate(views.ObjectCreate, CommunityEdit):
  title = _l("Create community")
  decorators = [require_admin]
  template = views.ObjectCreate.template
  base_template = views.ObjectCreate.base_template

  def breadcrumb(self):
    return nav.BreadcrumbItem(label=_(u'Create new community'))

  def message_success(self):
    return _(u"Community %(name)s created successfully", name=self.obj.name)


add_url('/new',
        view_func=CommunityCreate.as_view('new', view_endpoint='.community'))


class CommunityDelete(BaseCommunityView, views.ObjectDelete):
  get_form_kwargs = views.ObjectDelete.get_form_kwargs


add_url("/<string:community_id>/destroy",
        methods=['POST'],
        view_func=CommunityDelete.as_view(
          'delete',
          message_success=_l(u"Community destroyed.")))

## Community Image
_DEFAULT_IMAGE = Path(__file__).parent / u'data' / u'community.png'
_DEFAULT_IMAGE_MD5 = hashlib.md5(_DEFAULT_IMAGE.open('rb').read()).hexdigest()
route('/_default_image')(
  image_views.StaticImageView.as_view('community_default_image',
                                      set_expire=True,
                                      image=_DEFAULT_IMAGE,)
)

class CommunityImageView(image_views.BlobView):
  id_arg = 'blob_id'

  def prepare_args(self, args, kwargs):
    community = g.community
    if not community:
      raise NotFound()

    kwargs[self.id_arg] = community.image.id
     #image = open(join(dirname(__file__), "data", "community.png"), 'rb')
    return super(CommunityImageView, self).prepare_args(args, kwargs)


image = CommunityImageView.as_view('image', max_size=500, set_expire=True)
route("/<string:community_id>/image")(image)


def image_url(community, **kwargs):
  """
  return proper URL for image url
  """
  if not community or not community.image:
    kwargs['md5'] = _DEFAULT_IMAGE_MD5
    return url_for('communities.community_default_image', **kwargs)

  kwargs['community_id'] = community.slug
  kwargs['md5'] = community.image.md5
  return url_for('communities.image', **kwargs)


@route("/<string:community_id>/members")
@tab('members')
def members():
  g.breadcrumb.append(nav.BreadcrumbItem(
    label=_(u'Members'),
    url=nav.Endpoint('communities.members', community_id=g.community.slug))
  )

  memberships = User.query\
      .join(Membership)\
      .filter(Membership.community == g.community)\
      .add_columns(Membership.id, Membership.role)\
      .order_by(User.last_name.asc(), User.first_name.asc())\
      .all()

  return render_template("community/members.html",
                         memberships=memberships,
                         csrf_token=csrf.field())


@route("/<string:community_id>/members", methods=["POST"])
@csrf.protect
@require_manage
def members_post():
  community = g.community._model
  action = request.form.get("action")

  if action in ('add-user-role', 'set-user-role',):
    role = request.form.get("role").lower()
    user_id = int(request.form["user"])
    user = User.query.get(user_id)

    community.set_membership(user, role)

    if action == 'add-user-role':
      app = current_app._get_current_object()
      activity.send(app, actor=user, verb="join", object=community)

    db.session.commit()
    return redirect(url_for(".members", community_id=community.slug))

  elif action == 'delete':
    user_id = int(request.form['user'])
    user = User.query.get(user_id)
    membership_id = int(request.form['membership'])
    membership = Membership.query.get(membership_id)
    if membership.user_id != user_id:
      abort(500)

    community.remove_membership(user)

    app = current_app._get_current_object()
    activity.send(app, actor=user, verb="leave", object=community)

    db.session.commit()
    return redirect(url_for(".members", community_id=community.slug))

  else:
    raise BadRequest('Unknown action: {}'.format(repr(action)))


#
# Hack to redirect from urls used by the search engine.
#
@route("/doc/<int:doc_id>")
def doc(doc_id):
  doc = Document.query.get(doc_id)

  if doc is None:
    abort(404)

  folder = doc.parent
  while True:
    parent = folder.parent
    if parent.is_root_folder:
      break
    folder = parent
  community = Community.query.filter(Community.folder_id == folder.id).one()
  return redirect(url_for("documents.document_view",
                          community_id=community.slug, doc_id=doc.id))
