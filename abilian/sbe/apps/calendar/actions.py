from flask import g, url_for
from flask_login import current_user

from abilian.i18n import _l
from abilian.services import get_service
from abilian.services.security import Admin
from abilian.web.action import Action, FAIcon, actions


class CalendarAction(Action):
    def url(self, context=None):
        return url_for("." + self.name, community_id=g.community.slug)


class EventAction(CalendarAction):
    def pre_condition(self, context):
        event = context.get("object")
        return not not event

    def url(self, context=None):
        event = context.get("object")
        return url_for(
            "." + self.name, community_id=g.community.slug, event_id=event.id
        )


def is_admin(context):
    security = get_service("security")
    return security.has_role(current_user, Admin, object=context.get("object"))


_actions = [
    CalendarAction(
        "calendar:global", "new_event", _l("Create a new event"), icon="plus"
    ),
    CalendarAction("calendar:global", "index", _l("Upcoming events"), icon="list"),
    EventAction("calendar:event", "event", _l("View event"), icon=FAIcon("eye")),
    EventAction(
        "calendar:event", "event_edit", _l("Edit event"), icon=FAIcon("pencil")
    ),
]


def register_actions(state):
    if not actions.installed(state.app):
        return
    with state.app.app_context():
        actions.register(*_actions)
