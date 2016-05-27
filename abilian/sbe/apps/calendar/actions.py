# coding=utf-8

from __future__ import unicode_literals

from flask import current_app, g, url_for
from flask_login import current_user

from abilian.i18n import _l
from abilian.services.security import Admin
from abilian.web.action import Action, actions


class CalendarAction(Action):

    def url(self, context=None):
        if self._url or self.endpoint:
            return super(CalendarAction, self).url(context=context)

        return url_for("." + self.name, community_id=g.community.slug)


def is_admin(context):
    svc = current_app.services['security']
    return svc.has_role(current_user, Admin, object=context.get('object'))

# class ForumModalAction(ModalActionMixin, ThreadAction):
#     pass
#
#
# _close_template_action = u'''
# <form method="POST" action="{{ url }}" encoding="multipart/form-data">
#   {{ csrf.field() }}
#   <button type="submit" class="btn btn-link" name="action"
#           value="{{ action.name}}">
#     {%- if action.icon %}{{ action.icon }} {% endif %}
#     {{ action.title }}
#   </button>
# </form>
# '''

_actions = [
    CalendarAction('calendar:global',
                   'new_event',
                   _l('Create a new event'),
                   icon='plus'),
    CalendarAction('calendar:global',
                   'index',
                   _l('Upcoming events'),
                   icon='list'),

    # CalendarAction('calendar:global',
    #                'calendar_view',
    #                _l('Calendar view'),
    #                icon='calendar'),
]


def register_actions(state):
    if not actions.installed(state.app):
        return
    with state.app.app_context():
        actions.register(*_actions)
