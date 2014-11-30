# coding=utf-8
"""
"""
from __future__ import absolute_import

import logging
import hashlib
from cgi import escape
from os.path import dirname, join

from flask import (
  request, redirect, g, make_response, abort, jsonify, flash,
  current_app, Response, render_template)

import sqlalchemy as sa
from sqlalchemy.sql.expression import or_, and_, func, asc, desc, nullslast

from abilian.i18n import _
from abilian.core.models.subjects import User
from abilian.core.extensions import db, get_extension
from abilian.core.signals import activity
from abilian.services.image import crop_and_resize
from abilian.web import url_for, csrf
from abilian.web.views import default_view
from abilian.web.forms import widgets
from abilian.web.filters import age

from abilian.sbe.apps.communities.models import Membership
from abilian.sbe.apps.wall.views import get_recent_entries
from abilian.sbe.apps.wall.presenters import ActivityEntryPresenter
from ..forms import UserProfileForm, UserProfileViewForm
from .social import social
from .util import Env


logger = logging.getLogger(__name__)

DEFAULT_USER_MUGSHOT = open(join(dirname(__file__),
                                 "../../../static/images/silhouette_unknown.png")).read()

def make_tabs(user):
  return [
    dict(id='profile', label=_(u'Profile'), link=url_for(user, tab='profile')),
    #dict(id='conversations', label=_(u'Conversations'), link=url_for(user), is_online=True),
    dict(id='documents', label=_(u'Documents'), link=url_for(user, tab='documents')),
    dict(id='images', label=_(u'Images'), link=url_for(user, tab='images')),
    dict(id='audit', label=_(u'Audit'), link=url_for(user, tab='audit')),
  ]


@social.route("/users/")
def users():
  query = request.args.get("query")

  if query:
    query = query.replace("%", " ")
    q = or_(User.first_name.like("%" + query + "%"),
            User.last_name.like("%" + query + "%"))
    users = User.query.filter(q).limit(100).all()
  else:
    users = User.query.limit(100).all()
  ctx = dict(users=users)
  return render_template("social/users.html", **ctx)


# FIXME: Contact and Partenaire are not in the SBE package !
@social.route("/users/dt_json")
def users_dt_json():
  """JSON call to fill a DataTable. Needs some refactoring."""
  args = request.args

  length = int(args.get("iDisplayLength", 0))
  start = int(args.get("iDisplayStart", 0))
  sort_col = int(args.get("iSortCol_0", 1))
  sort_dir = args.get("sSortDir_0", "asc")
  echo = int(args.get("sEcho", 0))
  search = args.get("sSearch", "").replace("%", "").lower()

  end = start + length

  q = User.query
  total_count = q.count()

  q = q.options(
      sa.orm.joinedload(User.contact),
      sa.orm.noload(User.contact, Contact.communautes),
      sa.orm.joinedload(User.contact, Contact.partenaire),
  )

  if search:
    # TODO: gérer les accents
    filter = or_(func.lower(User.first_name).like("%" + search + "%"),
                 func.lower(User.last_name).like("%" + search + "%"),
                 func.lower(Partenaire.nom).like("%" + search + "%"))
    q = q.join(User.contact).\
          join(Contact.partenaire).\
          filter(filter).\
          reset_joinpoint()

  count = q.count()
  SORT_COLS = {
    1: [], # will be set to [User.last_name, User.first_name]
    2: [User.created_at],
    3: [User.last_active],
    }
  columns = list(SORT_COLS.get(sort_col, []))
  columns.extend([func.lower(User.last_name), func.lower(User.first_name)])

  direction = asc if sort_dir == 'asc' else desc
  order_by = map(direction, columns)

  # sqlite does not support 'NULLS FIRST|LAST' in ORDER BY clauses
  engine = q.session.get_bind(User.__mapper__)
  if engine.name != 'sqlite':
    order_by[0] = nullslast(order_by[0])

  q = q.order_by(*order_by)

  users = q.slice(start, end).all()

  data = []
  MUGSHOT_SIZE = 45
  for user in users:
    # TODO: this should be done on the browser.
    user_url = url_for(".user", user_id=user.id)
    mugshot = url_for(".user_mugshot", user_id=user.id, s=MUGSHOT_SIZE)
    name = escape(getattr(user, "name") or "")
    contact = user.contact
    job_title = escape((getattr(contact, "titre") if contact else None) or "")
    company = escape((getattr(contact.partenaire, "nom")
                     if contact and contact.partenaire else None)
                     or "")

    cell0 = (u'<a href="{url}"><img src="{src}" width="{size}" height="{size}">'
             '</a>'.format(url=user_url, src=mugshot, size=MUGSHOT_SIZE))
    cell1 = u'<div class="info"><a href="{user_url}">{name}</a> ' \
            '- {company} <p>{job_title}</p></div>'.format(**locals())
    cell2 = age(user.created_at)
    cell3 = age(user.last_active)

    cell4 = '' # TODO: follow / unfollow?
    data.append([cell0, cell1, cell2, cell3])

  result = {
    "sEcho": echo,
    "iTotalRecords": total_count,
    "iTotalDisplayRecords": count,
    "aaData": data,
  }
  return jsonify(result)


@social.route("/users/<int:user_id>")
@default_view(social, User, 'user_id')
def user(user_id):
  security = current_app.services['security']
  user = User.query.get(user_id)

  # FIXME: use user profiles
  view_form = UserProfileViewForm(obj=user)

  communities = [m.community for m in user.communautes_membership]
  if g.user != user and (not security.has_role(g.user, 'manager')):
    # filter visible communautes (ticket 165)
    communities = [c for c in communities if c.has_member(g.user)]

  view_form.communautes._set_data(communities)

  # FIXME
  contact = user
  env = Env(user=user,
            contact=contact,
            view_form=view_form,
            can_edit=can_edit(user),
            tabs=make_tabs(user))

  entries = get_recent_entries(user=user)
  entries = ActivityEntryPresenter.wrap_collection(entries)
  env.activity_entries = entries

  return render_template("social/user.html", **env)


# Older code is here.

#@social.route("/users/<int:user_id>")
#def user(user_id):
#  #user = User.query.options(
#  #  sa.orm.joinedload(User.contact),
#  #  sa.orm.lazyload('contact.communautes'),
#  #  ).get(user_id)
#  #contact = user.contact
#  #view_form = UserProfileViewForm(obj=contact)
#  #user = User.query.get(user_id)
#  #contact = user.contact
#  #view_form = UserProfileViewForm(obj=contact)
#  security = current_app.services['security']
#
#  communautes = [m.community for m in user.communautes_membership]
#  if g.user != user and (not security.has_role(g.user, 'manager')):
#    # filter visible communautes (ticket 165)
#    communautes = [c for c in communautes if c.has_member(g.user)]
#
#  view_form.communautes._set_data(communautes)
#
#  env = Env(user=user,
#            contact=contact,
#            view_form=view_form,
#            can_edit=can_edit(user),
#            tabs=make_tabs(user))
#
#  env.has_crm_access = security.has_role(g.user, "crm:user")
#
#  entries = get_recent_entries(user=user)
#  entries = ActivityEntryPresenter.wrap_collection(entries)
#  env.activity_entries = entries
#
#  return render_template("social/user.html", **env)


@social.route("/users/<int:user_id>/mugshot")
def user_mugshot(user_id):
  size = int(request.args.get('s', 55))
  if size > 500:
    raise ValueError("Error, size = %d" % size)
  user = User.query\
    .options(sa.orm.undefer(User.photo))\
    .get(user_id)

  if not user:
    abort(404)

  if user.photo:
    data = user.photo
  else:
    data = DEFAULT_USER_MUGSHOT

  etag = None

  if user.id == g.user.id:
    # FIXME: there should be a photo_digest field on user object
    acc = hashlib.md5(data)
    etag = acc.hexdigest()

    if request.if_none_match and etag in request.if_none_match:
      return Response(status=304)

  if size:
    data = crop_and_resize(data, size)

  response = make_response(data)
  response.headers['content-type'] = 'image/jpeg'

  if not user.id == g.user.id:
    response.headers.add('Cache-Control', 'public, max-age=600')
  else:
    # user always checks its own mugshot is up-to-date, in order to seeing old
    # one immediatly after having uploaded of a new picture.
    response.headers.add('Cache-Control', 'private, must-revalidate')
    response.set_etag(etag)

  return response


def can_edit(user):
  security = get_extension("security")
  if not security:
    return True

  # TODO: introduce a "self" role?
  return (user == g.user) or security.has_role(g.user, 'admin')

  # FIXME: introduce pluggable profiles?
  #has_contact = user.contact is not None
  #
  #return (has_contact and
  #        ((user == g.user) or security.has_role(g.user, 'admin')))


@social.route("/users/<int:user_id>/edit")
def user_edit(user_id):
  user = User.query.get(user_id)
  assert user is not None

  if not can_edit(user):
    return Response(status=403)

  contact = user.contact
  assert contact is not None

  form = UserProfileForm(obj=contact)
  form._widgets_options = { 'photo': dict(user_id=user_id) }
  panel = widgets.Panel(None, *[widgets.Row(f.name) for f in form])
  form_view = widgets.SingleView(UserProfileForm, panel)
  rendered_form = form_view.render_form(form)

  ctx = dict(rendered_entity=rendered_form, module=None)
  # FIXME: template is not in this package.
  return render_template("crm/single_view.html", **ctx)


@social.route("/users/<int:user_id>/edit", methods=['POST'])
@csrf.protect
def user_edit_post(user_id):
  user = User.query.get(user_id)
  assert user is not None

  if request.form.get('_action') == u'cancel':
    return redirect(url_for(".user", user_id=user_id))

  if not can_edit(user):
    return Response(status=403)

  # FIXME: introduce user profiles instead!
  contact = Contact.query.filter(Contact.user == user).first()
  assert contact is not None
  # FIXME: only for user and admin!

  form = UserProfileForm(obj=contact)
  if form.validate():
    form.populate_obj(contact)
    if form.photo.has_file() and hasattr(contact, 'photo'):
      # UserProfileForm has a photo field, but for it is not defined in Contact
      # schema but in User schema
      contact.user.photo = contact.photo.read()
      db.session.add(contact.user)
      del contact.photo

    db.session.add(contact)
    try:
      db.session.flush()
      activity.send(contact, actor=g.user, verb="update", object=contact)
      db.session.commit()
    except sa.exc.IntegrityError:
      db.session.rollback()
      logger.error('Error saving user profile',
                   exc_info=True, extra={'stack': True})
      flash(_(u'Error occured'), "error")
    except:
      db.session.rollback()
      logger.error('Unexpected error while saving user profile',
                   exc_info=True, extra={'stack': True})
      flash(_(u'Error occured'), "error")

    else:
      flash(_(u'Profile edited'), "success")
      return redirect(url_for(".user", user_id=user_id))
  else:
    flash(_(u'Please fix the error(s) below'), "error")

  return user_edit(user_id)


@social.route("/users/<int:user_id>", methods=['POST'])
def user_post(user_id):
  user = User.query.get(user_id)
  action = request.form.get('action')
  return_url = request.form.get('return_url')

  if action == 'follow':
    g.user.follow(user)
  elif action == 'unfollow':
    g.user.unfollow(user)
  else:
    raise Exception("Should not happen")
  db.session.commit()

  if return_url:
    # TODO: security check
    return redirect(return_url)
  else:
    return redirect(url_for(".user_view", user_id=user_id))


#
# Ad-hoc JSON endpoints, used by select boxes
#
@social.route("/users/json")
def users_json():
  q = request.args.get("q").replace("%", " ").lower()

  if not q or len(q) < 2:
    abort(500)

  query = User.query\
    .filter(or_(func.lower(User.first_name).like(q + "%"),
                func.lower(User.last_name).like(q + "%")))\
    .order_by(func.lower(User.last_name))

  with_membership = request.args.get('with_membership', None)
  if with_membership is not None:
    # provide membership info for a community
    with_membership = int(with_membership)
    query = query\
        .outerjoin(Membership,
                   and_(Membership.user.expression,
                        Membership.community_id == with_membership))\
        .add_columns(Membership.role)

  exclude_community = request.args.get('exclude_community', None)
  if exclude_community is not None:
    exclude_community = int(exclude_community)
    exclude = ~Membership.query\
        .filter(
            Membership.user.expression,
            Membership.community_id == exclude_community)\
        .options(sa.orm.noload('user'),
                 sa.orm.noload('community'))\
        .exists()
    query = query.filter(exclude)

  results = []
  for user in query.all():
    role = None
    if with_membership is not None:
      user, role = user

    if role is not None:
      role = unicode(role)

    item = {'id': user.id,
            'text': u'{} ({})'.format(user.name, user.email),
            'name': user.name,
            'email': user.email,
            'role': role,}
    results.append(item)

  return jsonify({'results': results})
