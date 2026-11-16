# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import url_for

from abilian.core.application import as_application
from abilian.core.extensions.login import authenticated_user
from abilian.i18n import _l
from abilian.sbe.apps.communities.actions import CommunityEndpoint
from abilian.sbe.apps.communities.security import can_manage
from abilian.web.action import Action, FAIcon, ModalActionMixin, actions

if TYPE_CHECKING:
    from flask.blueprints import BlueprintSetupState


class WikiPageAction(Action):
    Endpoint = CommunityEndpoint

    def pre_condition(self, context: dict[str, Any]) -> bool:
        page = context.get("object")
        return bool(page)

    def url(self, context=None):
        if self._url:
            return super().url(context)
        page = context.get("object")
        kw = self.endpoint.get_kwargs()
        kw["title"] = page.title
        return url_for(self.endpoint.name, **kw)


class WikiPageModalAction(ModalActionMixin, WikiPageAction):
    pass


class WikiAction(Action):
    Endpoint = CommunityEndpoint


_actions = (
    WikiPageAction(
        "wiki:page",
        "page_viewers",
        _l("Readers list"),
        icon="user",
        condition=lambda ctx: can_manage(authenticated_user(), ctx["object"].community),
        endpoint=".page_viewers",
    ),
    WikiPageAction(
        "wiki:page",
        "view",
        _l("View"),
        endpoint=".page",
        icon="eye",
    ),
    WikiPageAction(
        "wiki:page",
        "edit",
        _l("Edit"),
        endpoint=".page_edit",
        icon="pencil",
    ),
    WikiPageModalAction(
        "wiki:page",
        "upload_attachment",
        _l("Upload an attachment"),
        url="#upload-files",
        icon="plus",
    ),
    WikiPageAction(
        "wiki:page",
        "source",
        _l("Source"),
        endpoint=".page_source",
        icon=FAIcon("code"),
    ),
    WikiPageAction(
        "wiki:page",
        "changes",
        _l("Changes"),
        endpoint=".page_changes",
        icon="clock-o",
    ),
    WikiPageModalAction(
        "wiki:page",
        "delete",
        _l("Delete"),
        url="#modal-delete",
        icon="trash",
    ),
    WikiAction(
        "wiki:global",
        "new",
        _l("New page"),
        endpoint=".page_new",
        icon="plus",
    ),
    WikiAction(
        "wiki:global",
        "pages",
        _l("All pages"),
        endpoint=".wiki_pages",
        icon="list",
    ),
    WikiAction(
        "wiki:global",
        "help",
        _l("Syntax help"),
        endpoint=".wiki_help",
        icon="info-circle",
    ),
)


def register_actions(state: BlueprintSetupState) -> None:
    app = as_application(state.app)
    if not actions.installed(app):
        return

    with app.app_context():
        actions.register(*_actions)
