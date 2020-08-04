"""First cut at a notification system."""
from flask import current_app as app
from flask import request
from flask_login import current_user
from werkzeug.exceptions import MethodNotAllowed

from abilian.core.extensions import csrf, db
from abilian.core.models.subjects import User
from abilian.i18n import render_template_i18n
from abilian.sbe.apps.communities.security import require_admin
from abilian.sbe.apps.notifications import TOKEN_SERIALIZER_NAME
from abilian.services.auth.views import get_token_status

from ..tasks.social import make_message, send_daily_social_digest_to
from . import notifications

__all__ = ()

route = notifications.route


@require_admin
@route("/debug/social/")
def debug_social():
    """Send a digest to current user, or user with given email.

    Also displays the email in the browser as a result.
    """
    email = request.args.get("email")
    if email:
        user = User.query.filter(User.email == email).one()
    else:
        user = current_user

    msg = make_message(user)

    status = send_daily_social_digest_to(user)

    if status:
        return msg.html
    else:
        return "No message sent."


@route("/unsubscribe_sbe/<token>/", methods=["GET", "POST"])
@csrf.exempt
def unsubscribe_sbe(token: str) -> str:
    expired, invalid, user = get_token_status(token, TOKEN_SERIALIZER_NAME)
    if expired or invalid:
        return render_template_i18n("notifications/invalid-token.html")

    if request.method == "GET":
        return render_template_i18n(
            "notifications/confirm-unsubscribe.html", token=token
        )

    elif request.method == "POST":
        preferences = app.services["preferences"]
        preferences.set_preferences(user, **{"sbe:notifications:daily": False})
        db.session.commit()
        return render_template_i18n("notifications/unsubscribed.html", token=token)
    else:
        raise MethodNotAllowed()
