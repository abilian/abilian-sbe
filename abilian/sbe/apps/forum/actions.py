# coding=utf-8

from flask import g, url_for
from flask_babel import lazy_gettext as _l
from abilian.web.action import actions, Action, ModalActionMixin


class ForumAction(Action):
  def url(self, context=None):
    if self._url:
      return self._url
    return url_for("." + self.name, community_id=g.community.slug)


class ThreadAction(ForumAction):
  def pre_condition(self, context):
    thread = actions.context.get('object')
    return not not thread


def is_in_thread(context):
  thread = context.get('object')
  return not thread


class ForumModalAction(ModalActionMixin, ThreadAction):
  pass


_actions = (
  ForumAction('forum:global', 'new_thread',
              _l(u'Start a new conversation'), icon='plus'
  ),
  ForumAction('forum:global', 'index',
              _l(u'Recent conversations'), icon='list'
  ),
  ForumAction('forum:global', 'archives', _l(u'Archives'), icon='calendar'),
  ForumAction('forum:global', 'attachments',
              _l(u'Attachments'), icon='file',
              condition=is_in_thread
  ),
  ForumModalAction('forum:thread', 'delete', _l(u'Delete'),
                   url='#modal-delete', icon='trash'
  ),
  ThreadAction('forum:thread', 'attachments',
               _l(u'Attachments'), url='attachments', icon='file'
  ),
)


def register_actions(state):
  if not actions.installed(state.app):
    return
  with state.app.app_context():
    actions.register(*_actions)
