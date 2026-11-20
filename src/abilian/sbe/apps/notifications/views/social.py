# Copyright (c) 2012-2024, Abilian SAS

"""First cut at a notification system."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import request
from werkzeug.exceptions import MethodNotAllowed

from abilian.core.extensions import csrf, db
from abilian.core.extensions.login import authenticated
from abilian.core.models.subjects import User
from abilian.i18n import render_template_i18n
from abilian.sbe.apps.communities.decorators import is_site_admin
from abilian.sbe.apps.notifications import TOKEN_SERIALIZER_NAME
from abilian.sbe.apps.notifications.tasks.social import (
    make_message,
    send_daily_social_digest_to,
)
from abilian.services import get_service
from abilian.services.auth.views import get_token_status

from . import notifications

if TYPE_CHECKING:
    from abilian.services.preferences.service import PreferenceService

__all__ = ()

route = notifications.route


@route("/debug/social/")
@is_site_admin
@authenticated
def debug_social(user: User):
    """Send a digest to `user`, or to the user with the given email.

    Also displays the email in the browser as a result.
    """
    email = request.args.get("email")
    recipient = User.query.filter(User.email == email).one() if email else user

    msg = make_message(recipient)

    status = send_daily_social_digest_to(recipient)

    if status:
        return msg.html
    return "No message sent."


@route("/unsubscribe_sbe/<token>/", methods=["GET", "POST"])
@csrf.exempt
def unsubscribe_sbe(token: str) -> str:
    expired, invalid, user = get_token_status(token, TOKEN_SERIALIZER_NAME)
    if expired or invalid:
        return render_template_i18n("notifications/invalid-token.html")

    match request.method:
        case "GET":
            return render_template_i18n(
                "notifications/confirm-unsubscribe.html", token=token
            )

        case "POST":
            preferences = cast("PreferenceService", get_service("preferences"))
            preferences.set_preferences(user, **{"sbe:notifications:daily": False})
            db.session.commit()
            return render_template_i18n("notifications/unsubscribed.html", token=token)
    raise MethodNotAllowed
