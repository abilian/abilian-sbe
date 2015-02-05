"""
The blueprint for this app.
"""

from flask import Blueprint, redirect, g, url_for, render_template

from abilian.core import signals
from abilian.core.util import get_params
from abilian.core.extensions import db

from abilian.sbe.apps.wall.presenters import ActivityEntryPresenter
from abilian.sbe.apps.wall.util import get_recent_entries

from ..models import Message


__all__ = ['social']

MAX_LAST_USERS = 15
MAX_MESSAGES = 15

social = Blueprint("social", __name__,
                   url_prefix='/social', template_folder='../templates')
route = social.route


@social.before_request
def before_request():
  g.groups = g.user.groups
  g.groups.sort(lambda x, y: cmp(x.name, y.name))


@route("/")
def home():
  ctx = {}
  entries = get_recent_entries()
  entries = ActivityEntryPresenter.wrap_collection(entries)
  ctx['activity_entries'] = entries

  return render_template("social/home.html", **ctx)


@route("/stream/<stream_name>")
def stream(stream_name):
  pass


@route("/", methods=['POST'])
def share():
  # TODO: better error control / feedback
  d = get_params(Message.__editable__)
  if not d.get('content'):
    return redirect(url_for(".home"))

  message = Message(**d)
  db.session.add(message)

  #tags = message.tags
  #values = [ {'tag': tag, 'message_id': message.id} for tag in tags ]
  #db.engine.execute(tagging.insert(), values)

  db.session.commit()
  signals.entity_created.send(message)

  return redirect(url_for(".home"))
