from typing import Any, Dict

from flask import g
from flask import url_for as url_for_orig
from flask.blueprints import BlueprintSetupState
from flask_login import current_user

from abilian.i18n import _l
from abilian.sbe.apps.communities.security import is_manager
from abilian.services.security import MANAGE, WRITE, security
from abilian.web.action import Action, FAIcon, ModalActionMixin, actions

from .repository import repository


def url_for(endpoint, **kw):
    return url_for_orig(endpoint, community_id=g.community.slug, **kw)


class CmisContentAction(Action):
    sbe_type: str = ""
    permission: str = ""

    def __init__(self, *args, **kwargs) -> None:
        if "permission" in kwargs:
            self.permission = kwargs.pop("permission")

        Action.__init__(self, *args, **kwargs)

    def pre_condition(self, ctx: Dict[str, Any]) -> bool:
        obj = ctx["object"]
        ok = obj.sbe_type == self.sbe_type

        if ok and self.permission is not None:
            ok = self.has_access(self.permission, obj)

        return ok

    def has_access(self, permission: str, obj: Any) -> bool:
        return repository.has_permission(current_user, permission, obj)


class BaseFolderAction(CmisContentAction):
    """Apply to all folders, including root folder."""

    sbe_type = "cmis:folder"


class FolderButtonAction(BaseFolderAction):

    _std_template_string = (
        '<button class="btn {{ action.css_class }}" name="action" '
        'value="{{ action.name }}" title="{{ action.title }}">'
        "{{ action.icon }}</button>"
    )

    _modal_template_string = (
        '<a class="btn {{ action.css_class }}" href="{{ url }}" '
        'data-toggle="modal" role="button" title="{{ action.title }}">'
        "{{ action.icon }}</a>"
    )

    def __init__(self, *args, **kwargs) -> None:
        self.modal = False

        if "modal" in kwargs:
            self.modal = kwargs.pop("modal")

        css_class = kwargs.pop("css_class", "btn-default")
        self.CSS_CLASS = self.CSS_CLASS + " " + css_class

        BaseFolderAction.__init__(self, *args, **kwargs)

    @property
    def template_string(self):
        return self._modal_template_string if self.modal else self._std_template_string


class FolderAction(BaseFolderAction):
    """Apply to all folders except root folder."""

    sbe_type = "cmis:folder"

    def pre_condition(self, ctx):
        return (
            super().pre_condition(ctx) and ctx["object"] is not repository.root_folder
        )


class FolderPermisionsAction(BaseFolderAction):
    """Apply to all folders except root folder."""

    sbe_type = "cmis:folder"

    def pre_condition(self, ctx):
        return (
            super(BaseFolderAction, self).pre_condition(ctx) and ctx["object"].depth > 1
        )


class FolderModalAction(ModalActionMixin, FolderAction):
    pass


class DocumentAction(CmisContentAction):
    sbe_type = "cmis:document"


class DocumentModalAction(ModalActionMixin, DocumentAction):
    pass


class RootFolderAction(CmisContentAction):
    """Apply only for root folder."""

    def pre_condition(self, ctx):
        return ctx["object"] is repository.root_folder


_checkin_template_action = """
<form method="POST" action="{{ url }}" encoding="multipart/form-data" target="_new">
  {{ csrf.field() }}
  <button type="submit" class="btn btn-link" name="action"
          value="{{ action.name}}"
     onclick="window.setTimeout(function () { window.location.reload() }, 500)">
    {%- if action.icon %}{{ action.icon }} {% endif %}
    {{ action.title }}
  </button>
</form>
"""

_lock_template_action = """
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
    # Folder listing action buttons ##########
    FolderButtonAction(
        "documents:folder-listing", "download", _l("Download"), icon="download"
    ),
    FolderButtonAction(
        "documents:folder-listing",
        "move-files",
        _l("Move to another folder"),
        icon="move",
        url="#modal-move-files",
        modal=True,
        permission=WRITE,
    ),
    FolderButtonAction(
        "documents:folder-listing",
        "delete",
        _l("Delete"),
        permission=WRITE,
        icon="trash",
        css_class="btn-danger",
    ),
    FolderButtonAction(
        "documents:folder-listing",
        "change-owner",
        _l("Change owner"),
        icon="user",
        url="#modal-change-owner",
        modal=True,
        permission=MANAGE,
    ),
    # Folder left bar actions ##########
    # view
    RootFolderAction(
        "documents:content",
        "view",
        _l("List content"),
        icon="list",
        condition=(lambda ctx: security.has_role(current_user, "admin")),
        url=lambda ctx: url_for(".folder_view", folder_id=ctx["object"].id),
    ),
    # view
    FolderAction(
        "documents:content",
        "view",
        _l("List content"),
        icon="list",
        url=lambda ctx: url_for(".folder_view", folder_id=ctx["object"].id),
    ),
    # Descendants
    FolderAction(
        "documents:content",
        "descendants",
        _l("View descendants"),
        icon=FAIcon("code-fork fa-rotate-90"),
        url=lambda ctx: url_for(".descendants_view", folder_id=ctx["object"].id),
    ),
    # upload
    FolderModalAction(
        "documents:content",
        "upload_files",
        _l("Upload file(s)"),
        icon="upload",
        url="#modal-upload-files",
        permission=WRITE,
    ),
    # edit
    FolderModalAction(
        "documents:content",
        "edit",
        _l("Edit properties"),
        icon="pencil",
        url="#modal-edit",
        permission=WRITE,
    ),
    # new folder
    FolderModalAction(
        "documents:content",
        "new_folder",
        _l("New folder"),
        icon="plus",
        url="#modal-new-folder",
        permission=WRITE,
    ),
    # # members
    # FolderAction(
    #   'documents:content', 'members', _l('Members'), icon='user',
    #   url=lambda ctx: url_for(".members", folder_id=ctx['object'].id)),
    # permissions
    FolderPermisionsAction(
        "documents:content",
        "permissions",
        _l("Permissions"),
        icon="lock",
        url=lambda ctx: url_for(".permissions", folder_id=ctx["object"].id),
        permission=MANAGE,
    ),
    # Document actions ##########
    # View / preview in browser
    DocumentAction(
        "documents:content",
        "preview",
        _l("View in browser"),
        icon="eye-open",
        url=lambda ctx: url_for(".document_preview", doc_id=ctx["object"].id),
        condition=(
            lambda ctx: ctx["object"].antivirus_ok
            and ctx["object"].content_type
            in ("text/html", "text/plain", "application/pdf")
        ),
    ),
    # viewers
    DocumentModalAction(
        "documents:content",
        "document_viewers",
        _l("Viewers list"),
        icon="user",
        condition=lambda ctx: is_manager(context=ctx),
        url=lambda ctx: url_for(".document_viewers", doc_id=ctx["object"].id),
    ),
    # edit
    DocumentModalAction(
        "documents:content",
        "edit",
        _l("Edit properties"),
        icon="pencil",
        url="#modal-edit",
        permission=WRITE,
    ),
    # Checkin / Checkout
    DocumentAction(
        "documents:content",
        "checkout",
        _l("Checkout (Download for edit)"),
        icon="download",
        url=lambda ctx: url_for(".checkin_checkout", doc_id=ctx["object"].id),
        condition=lambda ctx: ctx["object"].lock is None,
        template_string=_checkin_template_action,
    ),
    # DocumentAction(
    #   'documents:content', 'lock', _l(u'Lock for edit'),
    #   icon='lock',
    #   url=lambda ctx: url_for('.checkin_checkout', doc_id=ctx['object'].id),
    #   condition=lambda ctx: ctx['object'].lock is None,
    #   template_string=_lock_template_action,
    # ),
    DocumentAction(
        "documents:content",
        "unlock",
        _l("Unlock"),
        icon=FAIcon("unlock"),
        url=lambda ctx: url_for(".checkin_checkout", doc_id=ctx["object"].id),
        condition=lambda ctx: ctx["object"].lock is not None,
        template_string=_lock_template_action,
    ),
    # upload-new / checkin
    DocumentModalAction(
        "documents:content",
        "upload",
        _l("Upload new version"),
        icon="upload",
        url="#modal-upload-new-version",
        # either not locked, either user is owner
        condition=lambda ctx: not ctx["object"].lock or ctx["object"].lock.is_owner(),
        permission=WRITE,
    ),
    # send by email
    DocumentModalAction(
        "documents:content",
        "send_by_email",
        _l("Send by email"),
        icon="envelope",
        url="#modal-send-by-email",
        condition=lambda ctx: ctx["object"].antivirus_ok,
        permission=WRITE,
    ),
    # delete
    DocumentModalAction(
        "documents:content",
        "delete",
        _l("Delete"),
        icon="trash",
        url="#modal-delete",
        permission=WRITE,
    ),
    # refresh preview
    DocumentAction(
        "documents:content",
        "refresh_preview",
        _l("Refresh preview"),
        icon="refresh",
        url=lambda ctx: url_for(".refresh_preview", doc_id=ctx["object"].id),
        condition=lambda ctx: ctx["object"].antivirus_ok,
        permission=MANAGE,
    ),
)


def register_actions(state: BlueprintSetupState) -> None:
    if not actions.installed(state.app):
        return

    with state.app.app_context():
        actions.register(*_actions)
