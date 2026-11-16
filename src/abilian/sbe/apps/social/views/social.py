# Copyright (c) 2012-2024, Abilian SAS

"""The blueprint for this app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import redirect, render_template, url_for

from abilian.core.extensions import db
from abilian.core.extensions.login import authenticated
from abilian.core.util import get_params
from abilian.sbe.apps.social.models import Message
from abilian.sbe.apps.wall.presenters import ActivityEntryPresenter
from abilian.sbe.apps.wall.util import get_recent_entries
from abilian.services.security import AUTHENTICATED
from abilian.web.access_blueprint import AccessControlBlueprint

if TYPE_CHECKING:
    from abilian.core.models.subjects import User

__all__ = ["social"]

MAX_LAST_USERS = 15
MAX_MESSAGES = 15

# The whole blueprint, not route by route: most routes here had no
# `@login_required`, and the user directory leaked to anonymous visitors.
social = AccessControlBlueprint(
    "social",
    __name__,
    url_prefix="/social",
    template_folder="../templates",
    allowed_roles=AUTHENTICATED,
)
route = social.route


@route("/")
@authenticated
def home(user: User) -> str:
    ctx = {}
    entries = get_recent_entries(user, num=50)
    entries = ActivityEntryPresenter.wrap_collection(entries)
    ctx["activity_entries"] = entries

    return render_template("social/home.html", **ctx)


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
