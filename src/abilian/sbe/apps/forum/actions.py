# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import g, request, url_for

from abilian.i18n import _l
from abilian.sbe.apps.communities.security import can_manage
from abilian.web.action import Action, FAIcon, ModalActionMixin, actions

if TYPE_CHECKING:
    from flask.blueprints import BlueprintSetupState


class ForumAction(Action):
    def is_current(self):
        return request.path == self.url()

    def is_filtered(self):
        filter_keys = ["today", "month", "year", "week"]
        current_url = request.path.split("/")
        filter = current_url[-1].strip()

        if filter not in filter_keys:
            return False

        return self.url() == "#filter"

    def url(self, context=None):
        if self._url or self.endpoint:
            return super().url(context=context)

        return url_for(f".{self.name}", community_id=g.community.slug)


class ThreadAction(ForumAction):
    def pre_condition(self, context):
        thread = actions.context.get("object")
        return bool(thread)


def can_moderate(context) -> bool:
    """Closing, reopening and deleting a thread: the community's managers.

    This asked `has_role(current_user, ADMIN, object=thread)`. Nothing ever
    grants a role on a Thread and `has_role` unions the global roles in
    regardless, so that was the site-wide answer wearing an object-scoped
    spelling: the manager of a community could not moderate its own forum,
    and only a site admin could.
    """
    return can_manage(context["object"].community)


def is_in_thread(context) -> bool:
    thread = context.get("object")
    return not thread


def is_closed(context):
    thread = context.get("object")
    return thread.closed


def not_closed(context) -> bool:
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
    ForumAction("forum:global", "index", _l("Recent conversations"), icon="comments"),
    ForumAction(
        "forum:global", "index/<string:filter>", _l("Top"), url="#filter", icon="fire"
    ),
    ForumAction("forum:global", "archives", _l("Archives"), icon="archive"),
    ForumAction(
        "forum:global", "attachments", _l("Attachments"), condition=is_in_thread
    ),
    ForumAction("forum:global", "new_thread", _l("New conversation"), icon="plus"),
    ForumModalAction(
        "forum:thread",
        "delete",
        _l("Delete"),
        condition=lambda ctx: can_moderate(ctx) and not_closed(ctx),
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
        condition=lambda ctx: can_moderate(ctx) and not_closed(ctx),
        icon=FAIcon("lock"),
    ),
    ThreadAction(
        "forum:thread",
        "reopen",
        _l("Re-open thread"),
        url="close",
        template_string=_close_template_action,
        condition=lambda ctx: can_moderate(ctx) and is_closed(ctx),
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
