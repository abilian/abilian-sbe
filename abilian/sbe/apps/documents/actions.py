# coding=utf-8
from flask import g, url_for as url_for_orig
from flask.ext.babel import lazy_gettext as _l

from abilian.web.action import actions, Action, ModalActionMixin
from abilian.services.security import security

from .repository import repository


def url_for(endpoint, **kw):
  return url_for_orig(endpoint, community_id=g.community.slug, **kw)


class CmisContentAction(Action):
  sbe_type = None
  permission = None

  def __init__(self, *args, **kwargs):
    if 'permission' in kwargs:
      self.permission = kwargs.pop('permission')

    Action.__init__(self, *args, **kwargs)

  def pre_condition(self, ctx):
    obj = ctx['object']
    ok = obj.sbe_type == self.sbe_type

    if ok and self.permission is not None:
      ok = self.has_access(self.permission, obj)

    return ok

  def has_access(self, permission, obj):
    return repository.has_permission(g.user, permission, obj)


class BaseFolderAction(CmisContentAction):
  """ Apply to all folders, including root folder
  """
  sbe_type = u'cmis:folder'


class FolderButtonAction(BaseFolderAction):
  """
  """
  _std_template_string = (
    u'<button class="btn {{ action.css_class }}" name="action" '
    u'value="{{ action.name }}" title="{{ action.title }}">'
    u'{{ action.icon }}</button>')

  _modal_template_string = (
    u'<a class="btn {{ action.css_class }}" href="{{ url }}" '
    u'data-toggle="modal" role="button" title="{{ action.title }}">'
    u'{{ action.icon }}</a>')

  def __init__(self, *args, **kwargs):
    self.modal = False

    if 'modal' in kwargs:
      self.modal = kwargs.pop('modal')

    css_class = kwargs.pop('css_class', u'btn-default')
    self.CSS_CLASS = self.CSS_CLASS + u' ' + css_class

    BaseFolderAction.__init__(self, *args, **kwargs)

  @property
  def template_string(self):
    return (self._modal_template_string
            if self.modal
            else self._std_template_string)


class FolderAction(BaseFolderAction):
  """ Apply to all folders except root folder
  """
  sbe_type = u'cmis:folder'

  def pre_condition(self, ctx):
    return (super(FolderAction, self).pre_condition(ctx)
            and ctx['object'] is not repository.root_folder)


class FolderPermisionsAction(BaseFolderAction):
  """ Apply to all folders except root folder
  """
  sbe_type = u'cmis:folder'

  def pre_condition(self, ctx):
    return (super(BaseFolderAction, self).pre_condition(ctx)
            and ctx['object'].depth > 1)


class FolderModalAction(ModalActionMixin, FolderAction):
  """
  """

class DocumentAction(CmisContentAction):
  sbe_type = u'cmis:document'


class DocumentModalAction(ModalActionMixin, DocumentAction):
  """
  """


class RootFolderAction(CmisContentAction):
  """ Apply only for root folder
  """
  def pre_condition(self, ctx):
    return ctx['object'] is repository.root_folder


_actions = (
  # Folder listing action buttons ##########
  FolderButtonAction(
    'documents:folder-listing', 'download', _l(u'Download'),
    icon='download'),
  FolderButtonAction(
    'documents:folder-listing', 'move-files', _l(u'Move to another folder'),
    icon='move', url='#modal-move-files', modal=True,
    permission='write'),
  FolderButtonAction(
    'documents:folder-listing', 'delete', _l(u'Delete'),
    permission='write',
    icon='trash', css_class='btn-danger'),

  # Folder left bar actions ##########
  # view
  RootFolderAction(
    'documents:content', 'view', _l(u'List content'), icon='list',
    condition=(lambda ctx: security.has_role(g.user, "admin")),
    url=lambda ctx: url_for(".folder_view", folder_id=ctx['object'].id),),
  # view
  FolderAction(
    'documents:content', 'view', _l(u'List content'), icon='list',
    url=lambda ctx: url_for(".folder_view", folder_id=ctx['object'].id),),
  # upload
  FolderModalAction(
    'documents:content', 'upload_files', _l('Upload file(s)'),
    icon='upload', url='#modal-upload-files',
    permission='write'),
  # edit
  FolderModalAction(
    'documents:content', 'edit', _l('Edit'),
    icon='pencil', url='#modal-edit',
    permission='write'),
  # new folder
  FolderModalAction(
    'documents:content', 'new_folder', _l('New folder'),
    icon='plus', url='#modal-new-folder',
    permission='write'),

  # # members
  # FolderAction(
  #   'documents:content', 'members', _l('Members'), icon='user',
  #   url=lambda ctx: url_for(".members", folder_id=ctx['object'].id)),

  # permissions
  FolderPermisionsAction(
    'documents:content', 'permissions', _l('Permissions'), icon='lock',
    url=lambda ctx: url_for(".permissions", folder_id=ctx['object'].id),
    permission='manage'),

  # Document actions ##########
  # download "inline"
  DocumentAction(
      'documents:content', 'download', _l(u'View in browser'),
      icon='eye-open',
      url=lambda ctx: url_for('.document_download', doc_id=ctx['object'].id),
      condition=(
          lambda ctx:
          ctx['object'].antivirus_ok
          and ctx['object'].content_type in ('text/html',
                                             'text/plain',
                                             'application/pdf'))
  ),
  # download "attached"
  DocumentAction(
      'documents:content', 'download_attachment', _l(u'Download'),
      icon='download',
      url=lambda ctx: url_for('.document_download', doc_id=ctx['object'].id,
                              attach=True),
      condition=(lambda ctx: ctx['object'].antivirus_ok),
  ),
  # edit
  DocumentModalAction(
    'documents:content', 'edit', _l(u'Edit'),
    icon='pencil', url='#modal-edit',
    permission='write'),
  # upload-new
  DocumentModalAction(
      'documents:content', 'upload', _l(u'Upload new version'),
      icon='upload', url='#modal-upload-new-version',
      permission='write'),
  # send by email
  DocumentModalAction(
      'documents:content', 'send_by_email', _l(u'Send by email'),
      icon='envelope', url='#modal-send-by-email',
      condition=lambda ctx: ctx['object'].antivirus_ok,
      permission='write'),
  # delete
  DocumentModalAction(
      'documents:content', 'delete', _l(u'Delete'),
      icon='trash', url='#modal-delete',
      permission='write'),
  # refresh preview
  DocumentAction(
      'documents:content', 'refresh_preview', _l(u'Refresh preview'),
      icon='refresh',
      url=lambda ctx: url_for('.refresh_preview', doc_id=ctx['object'].id),
      condition=lambda ctx: ctx['object'].antivirus_ok,
      permission='manage',),
  )


def register_actions(state):
  if not actions.installed(state.app):
    return

  with state.app.app_context():
    actions.register(*_actions)
