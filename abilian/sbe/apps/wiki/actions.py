# coding=utf-8
from flask import url_for
from flask_babel import lazy_gettext as _l

from abilian.sbe.apps.communities.actions import CommunityEndpoint
from abilian.web.action import Action, FAIcon, ModalActionMixin, actions


class WikiPageAction(Action):
    Endpoint = CommunityEndpoint

    def pre_condition(self, context):
        page = context.get('object')
        return bool(page)

    def url(self, context=None):
        if self._url:
            return self._url
        else:
            page = context.get('object')
            kw = self.endpoint.get_kwargs()
            kw['title'] = page.title
            return url_for(self.endpoint.name, **kw)


class WikiPageModalAction(ModalActionMixin, WikiPageAction):
    pass


class WikiAction(Action):
    Endpoint = CommunityEndpoint


_actions = (WikiPageAction('wiki:page',
                           'view',
                           _l(u'View'),
                           endpoint='.page',
                           icon='eye-open'),
            WikiPageAction('wiki:page',
                           'edit',
                           _l(u'Edit'),
                           endpoint='.page_edit',
                           icon='pencil'),
            WikiPageModalAction('wiki:page',
                                'upload_attachment',
                                _l(u'Upload an attachment'),
                                url='#upload-files',
                                icon='plus'),
            WikiPageAction('wiki:page',
                           'source',
                           _l(u'Source'),
                           endpoint='.page_source',
                           icon=FAIcon('code')),
            WikiPageAction('wiki:page',
                           'changes',
                           _l(u'Changes'),
                           endpoint='.page_changes',
                           icon='time'),
            WikiPageModalAction('wiki:page',
                                'delete',
                                _l(u'Delete'),
                                url='#modal-delete',
                                icon='trash'),
            WikiAction('wiki:global',
                       'new',
                       _l(u'New page'),
                       endpoint='.page_new',
                       icon='plus'),
            WikiAction('wiki:global',
                       'pages',
                       _l(u'All pages'),
                       endpoint='.wiki_pages',
                       icon='list'),
            WikiAction('wiki:global',
                       'help',
                       _l(u'Syntax help'),
                       endpoint='.wiki_help',
                       icon='info-sign'),)


def register_actions(state):
    if not actions.installed(state.app):
        return

    with state.app.app_context():
        actions.register(*_actions)
