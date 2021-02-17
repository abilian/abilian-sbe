"""The blueprint for this app."""

from flask import Blueprint, redirect, render_template, url_for

from abilian.core.extensions import db
from abilian.core.util import get_params
from abilian.sbe.apps.social.models import Message
from abilian.sbe.apps.wall.presenters import ActivityEntryPresenter
from abilian.sbe.apps.wall.util import get_recent_entries

__all__ = ["social"]

MAX_LAST_USERS = 15
MAX_MESSAGES = 15

social = Blueprint(
    "social", __name__, url_prefix="/social", template_folder="../templates"
)
route = social.route


@route("/")
def home() -> str:
    ctx = {}
    entries = get_recent_entries(num=50)
    entries = ActivityEntryPresenter.wrap_collection(entries)
    ctx["activity_entries"] = entries

    return render_template("social/home.html", **ctx)


@route("/stream/<stream_name>")
def stream(stream_name):
    pass


@route("/", methods=["POST"])
def share():
    # TODO: better error control / feedback
    d = get_params(Message.__editable__)
    if not d.get("content"):
        return redirect(url_for(".home"))

    message = Message(**d)
    db.session.add(message)

    # tags = message.tags
    # values = [ {'tag': tag, 'message_id': message.id} for tag in tags ]
    # db.engine.execute(tagging.insert(), values)

    db.session.commit()
    return redirect(url_for(".home"))
