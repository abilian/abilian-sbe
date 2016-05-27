# coding=utf-8
"""
Forum views
"""
from __future__ import absolute_import, print_function, unicode_literals

from datetime import date, datetime
from itertools import groupby
from urllib import quote

import sqlalchemy as sa
from flask import (current_app, flash, g, make_response, render_template,
                   request)
from flask_babel import format_date
from flask_login import current_user
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import BadRequest, NotFound

from abilian.core.util import utc_dt
from abilian.i18n import _, _l
from abilian.sbe.apps.calendar.forms import EventForm
from abilian.sbe.apps.calendar.models import Event
from abilian.sbe.apps.communities.blueprint import Blueprint
from abilian.sbe.apps.communities.views import default_view_kw
from abilian.web import url_for, views
from abilian.web.action import ButtonAction, Endpoint
from abilian.web.nav import BreadcrumbItem
from abilian.web.views import default_view

blueprint = Blueprint("calendar",
                      __name__,
                      url_prefix="/calendar",
                      template_folder="templates")
route = blueprint.route


@route('/')
def index():
    return render_template('calendar/index.html')


class BaseEventView(object):
    Model = Event
    Form = EventForm
    pk = 'event_id'
    base_template = 'community/_base.html'

    def index_url(self):
        return url_for(".index", community_id=g.community.slug)

    def view_url(self):
        return url_for(self.obj)


class EventCreateView(BaseEventView, views.ObjectCreate):
    POST_BUTTON = ButtonAction('form',
                               'create',
                               btn_class='primary',
                               title=_l('Post this event'))

    title = _("New event")

    def init_object(self, args, kwargs):
        args, kwargs = super(EventCreateView, self).init_object(args, kwargs)
        self.event = self.obj
        return args, kwargs

    @property
    def activity_target(self):
        return self.event.community

    def get_form_buttons(self, *args, **kwargs):
        return [self.POST_BUTTON, views.object.CANCEL_BUTTON]


route('/new_event/')(EventCreateView.as_view(b'new_event',
                                             view_endpoint='.event'))
