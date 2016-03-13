# coding=utf-8
from os.path import dirname, join

from flask import (current_app, flash, g, jsonify, make_response, redirect,
                   render_template, request, url_for)
from flask_babel import gettext as _
from sqlalchemy import func
from werkzeug.exceptions import InternalServerError, NotFound

from abilian.core.extensions import db
from abilian.core.models.subjects import Group, User
from abilian.services.image import CROP, resize
from abilian.services.security import security
from abilian.web import csrf
from abilian.web.views import default_view

from .social import social
from .util import Env

DEFAULT_GROUP_MUGSHOT = open(join(
    dirname(__file__), "../../../static/images/frog.jpg")).read()


@social.route("/groups/")
def groups():
    tab = request.args.get("tab", "all_groups")
    e = Env()
    if tab == 'all_groups':
        e.groups = Group.query.order_by(Group.name).all()
        if not security.has_role(g.user, "admin"):
            e.groups = [group
                        for group in e.groups
                        if group.public or g.user in group.members]
    else:
        e.groups = g.user.groups
        e.groups.sort(key=lambda x: x.name)
    return render_template("social/groups.html", **e)


def is_admin(group):
    is_admin = g.user in group.admins
    if not is_admin and 'security' in current_app.extensions:
        is_admin = current_app.services['security'].has_role(g.user, 'admin')

    return is_admin


@social.route("/groups/<int:group_id>")
@default_view(social, Group, 'group_id')
def group_home(group_id):
    e = Env(csrf_token=csrf.field())
    e.group = Group.query.get(group_id)
    e.is_admin = is_admin(e.group)
    return render_template("social/group.html", **e)


@social.route("/groups/<int:group_id>/json")
def group_json(group_id):
    members = Group.query.get(group_id).members
    q = request.args.get("q", u'').lower()
    if q:
        members = filter(
            lambda u: any(term.startswith(q)
                          for name in (u.first_name.lower(), u.last_name.lower())
                          for term in name.split()),
            members)

    result = {'results': [{'id': obj.id, 'text': obj.name} for obj in members]}
    return jsonify(result)


@social.route("/groups/<int:group_id>", methods=['POST'])
@csrf.protect
def group_post(group_id):
    group = Group.query.get(group_id)
    action = request.form.get('action')
    return_url = request.form.get('return_url')

    membership_actions = frozenset(('add',
                                    'remove',
                                    'add-admin',
                                    'remove-admin',))

    if action not in ('join', 'leave'):
        assert is_admin(group)

    if action == 'join':
        g.user.join(group)
    elif action == 'leave':
        g.user.leave(group)
    elif action in membership_actions:
        user_id = request.form.get('user', u'').strip()
        try:
            user_id = int(user_id)
        except:
            flash(_(u'Error: No user selected'), 'error')
            return redirect(url_for(".group_home", group_id=group_id))

        user = User.query.get(user_id)

        if action == 'add':
            user.join(group)
        elif action == 'remove':
            user.leave(group)
        elif action == 'add-admin':
            if user not in group.admins:
                group.admins.append(user)
        elif action == 'remove-admin':
            if user in group.admins:
                group.admins.remove(user)
    else:
        raise Exception("Should not happen")
    db.session.commit()

    if return_url:
        # TODO: security check
        return redirect(return_url)
    else:
        return redirect(url_for(".group_home", group_id=group_id))


@social.route("/groups/new")
def groups_new():
    # TODO later
    return

    # e = Env()
    # e.form = GroupForm()
    # return render_template("social/groups-new.html", **e)


@social.route("/groups/new", methods=['POST'])
def groups_new_post():
    # TODO later
    return

    # form = GroupForm()
    #
    # if form.validate():
    #     group = Group()
    #     form.populate_obj(group)
    #     db.session.add(group)
    #     db.session.commit()
    #     flash(_(u"Your new group has been created"), category='info')
    #     return redirect(url_for('.group_home', group_id=group.id))
    #
    # else:
    #     e = Env()
    #     e.form = form
    #     return render_template("social/groups-new.html", **e)


@social.route("/groups/<int:group_id>/mugshot")
def group_mugshot(group_id):
    # TODO: duplicated code (with user_mugshot). Extract common method.
    size = int(request.args.get('s', 55))
    if size > 500:
        raise ValueError("Error, size = %d" % size)
    group = Group.query.get(group_id)

    if not group:
        raise NotFound()

    if group.photo:
        data = group.photo
    else:
        data = DEFAULT_GROUP_MUGSHOT

    if size:
        data = resize(data, size, size, mode=CROP)

    response = make_response(data)
    response.headers['content-type'] = 'image/jpeg'
    response.headers.add('Cache-Control', 'public, max-age=600')
    return response


#
# Ad-hoc JSON endpoints, used by select boxes
#
@social.route("/groups/json")
def groups_json():
    q = request.args.get("q").replace("%", " ").lower()

    if not q or len(q) < 2:
        raise InternalServerError()

    query = Group.query
    #query = query.filter(func.lower(Group.name).like(q + "%"))
    query = query.order_by(func.lower(Group.name))
    all = query.all()

    result = {'results': [{'id': obj.id, 'text': obj.name} for obj in all]}
    return jsonify(result)
