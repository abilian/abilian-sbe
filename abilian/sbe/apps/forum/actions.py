from typing import cast

from flask import g, request, url_for
from flask.blueprints import BlueprintSetupState
from flask_login import current_user

from abilian.i18n import _l
from abilian.services import get_service
from abilian.services.security import Admin, SecurityService
from abilian.web.action import Action, FAIcon, ModalActionMixin, actions


class ForumAction(Action):
    def is_current(self):
        return request.path == self.url()

    def is_filtered(self):
        filter_keys = ["today", "month", "year", "week"]
        current_url = request.path.split("/")
        filter = current_url[-1].strip()

        if filter not in filter_keys:
            return False

        if self.url() == "#filter":
            return True

        return False

    def url(self, context=None):
        if self._url or self.endpoint:
            return super().url(context=context)

        return url_for("." + self.name, community_id=g.community.slug)


class ThreadAction(ForumAction):
    def pre_condition(self, context):
        thread = actions.context.get("object")
        return not not thread


def is_admin(context):
    security = cast(SecurityService, get_service("security"))
    return security.has_role(current_user, Admin, object=context.get("object"))


def is_in_thread(context):
    thread = context.get("object")
    return not thread


def is_closed(context):
    thread = context.get("object")
    return thread.closed


def not_closed(context):
    return not is_closed(context)


class ForumModalAction(ModalActionMixin, ThreadAction):
    pass


_close_template_action = """
<form method="POST" action="{{ url }}" encoding="multipart/form-data">
  {{ csrf.field() }}
  <button type="submit" class="btn btn-link" name="action"
          value="{{ action.name}}">
    {%- if action.icon %}{{ action.icon }} {% endif %}
    {{ action.title }}
  </button>
</form>
"""

_actions = (
    ForumAction("forum:global", "index", _l("Recent conversations")),
    ForumAction("forum:global", "index/<string:filter>", _l("Top"), url="#filter"),
    ForumAction("forum:global", "archives", _l("Archives")),
    ForumAction(
        "forum:global", "attachments", _l("Attachments"), condition=is_in_thread
    ),
    ForumAction("forum:global", "new_thread", _l("New conversation"), icon="plus"),
    ForumModalAction(
        "forum:thread",
        "delete",
        _l("Delete"),
        condition=lambda ctx: is_admin(ctx) and not_closed(ctx),
        url="#modal-delete",
        icon="trash",
    ),
    #
    ThreadAction(
        "forum:thread",
        "close",
        _l("Close thread"),
        url="close",
        template_string=_close_template_action,
        condition=lambda ctx: is_admin(ctx) and not_closed(ctx),
        icon=FAIcon("lock"),
    ),
    ThreadAction(
        "forum:thread",
        "reopen",
        _l("Re-open thread"),
        url="close",
        template_string=_close_template_action,
        condition=lambda ctx: is_admin(ctx) and is_closed(ctx),
        icon=FAIcon("unlock"),
    ),
    ThreadAction(
        "forum:thread", "attachments", _l("Attachments"), url="attachments", icon="file"
    ),
)


def register_actions(state: BlueprintSetupState) -> None:
    if not actions.installed(state.app):
        return
    with state.app.app_context():
        actions.register(*_actions)
