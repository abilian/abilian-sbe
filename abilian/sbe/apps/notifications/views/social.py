# coding=utf-8
"""
First cut at a notification system.
"""
from __future__ import absolute_import

from werkzeug.exceptions import MethodNotAllowed
from flask import current_app as app, request
from flask.ext.login import current_user
from abilian.i18n import render_template_i18n
from abilian.core.extensions import db, csrf
from abilian.core.models.subjects import User
from abilian.services.auth.views import get_token_status
from abilian.sbe.apps.communities.security import require_admin

from abilian.sbe.apps.notifications import TOKEN_SERIALIZER_NAME
from ..tasks.social import send_daily_social_digest_to, make_message
from . import notifications

__all__ = []

route = notifications.route

@require_admin
@route("/debug/social/")
def debug_social():
  """Send a digest to current user, or user with given email.

  Also displays the email in the browser as a result.
  """
  email = request.args.get('email')
  if email:
    user = User.query.filter(User.email == email).one()
  else:
    email = current_user.email
    user = current_user

  msg = make_message(user)

  status = send_daily_social_digest_to(user)

  if status:
    return msg.html
  else:
    return "No message sent."


@route("/unsubscribe_sbe/<token>/", methods=['GET', 'POST'])
@csrf.exempt
def unsubscribe_sbe(token):
  expired, invalid, user = get_token_status(token, TOKEN_SERIALIZER_NAME)
  if expired or invalid:
    return render_template_i18n("notifications/invalid-token.html")

  if request.method == 'GET':
    return render_template_i18n("notifications/confirm-unsubscribe.html",
                           token=token)

  elif request.method == 'POST':
    preferences = app.services['preferences']
    preferences.set_preferences(user, **{'sbe:notifications:daily': False})
    db.session.commit()
    return render_template_i18n("notifications/unsubscribed.html",
                           token=token)
  else:
    raise MethodNotAllowed()
