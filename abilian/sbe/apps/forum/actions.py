# coding=utf-8

from flask import current_app, g, url_for
from flask_login import current_user

from abilian.i18n import _l
from abilian.services.security import Admin
from abilian.web.action import Action, FAIcon, ModalActionMixin, actions


class ForumAction(Action):

    def url(self, context=None):
        if self._url or self.endpoint:
            return super(ForumAction, self).url(context=context)

        return url_for("." + self.name, community_id=g.community.slug)


class ThreadAction(ForumAction):

    def pre_condition(self, context):
        thread = actions.context.get('object')
        return not not thread


def is_admin(context):
    svc = current_app.services['security']
    return svc.has_role(current_user, Admin, object=context.get('object'))


def is_in_thread(context):
    thread = context.get('object')
    return not thread


def is_closed(context):
    thread = context.get('object')
    return thread.closed


def not_closed(context):
    return not is_closed(context)


class ForumModalAction(ModalActionMixin, ThreadAction):
    pass


_close_template_action = u'''
<form method="POST" action="{{ url }}" encoding="multipart/form-data">
  {{ csrf.field() }}
  <button type="submit" class="btn btn-link" name="action"
          value="{{ action.name}}">
    {%- if action.icon %}{{ action.icon }} {% endif %}
    {{ action.title }}
  </button>
</form>
'''

_actions = (
    ForumAction('forum:global',
                'new_thread',
                _l(u'Start a new conversation'),
                icon='plus'),
    ForumAction('forum:global',
                'index',
                _l(u'Recent conversations'),
                icon='list'),
    ForumAction('forum:global',
                'archives',
                _l(u'Archives'),
                icon='calendar'),
    ForumAction('forum:global',
                'attachments',
                _l(u'Attachments'),
                icon='file',
                condition=is_in_thread),
    ForumModalAction('forum:thread',
                     'delete',
                     _l(u'Delete'),
                     condition=lambda ctx: is_admin(ctx) and not_closed(ctx),
                     url='#modal-delete',
                     icon='trash'),
    ThreadAction('forum:thread',
                 'close',
                 _l('Close thread'),
                 url='close',
                 template_string=_close_template_action,
                 condition=lambda ctx: is_admin(ctx) and not_closed(ctx),
                 icon=FAIcon('lock')),
    ThreadAction('forum:thread',
                 'reopen',
                 _l('Re-open thread'),
                 url='close',
                 template_string=_close_template_action,
                 condition=lambda ctx: is_admin(ctx) and is_closed(ctx),
                 icon=FAIcon('unlock')),
    ThreadAction('forum:thread',
                 'attachments',
                 _l(u'Attachments'),
                 url='attachments',
                 icon='file'),)


def register_actions(state):
    if not actions.installed(state.app):
        return
    with state.app.app_context():
        actions.register(*_actions)
