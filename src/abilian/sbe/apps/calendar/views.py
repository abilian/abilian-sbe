# Copyright (c) 2012-2024, Abilian SAS

"""A community's calendar: its events to come or past, by month, the month at a
glance beside them; an event, and adding it to one's own calendar; making,
changing and deleting one."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from flask import g, render_template, request
from toolz import groupby
from werkzeug.exceptions import BadRequest, Forbidden
from werkzeug.wrappers import Response

from abilian.core.extensions.login import authenticated_user
from abilian.core.util import utcnow
from abilian.i18n import _l
from abilian.sbe.apps.communities.blueprint import (
    CommunityBlueprint,
    in_community,
    with_tool,
)
from abilian.sbe.apps.communities.security import can_manage
from abilian.sbe.apps.communities.views import default_view_kw
from abilian.web import url_for, views
from abilian.web.action import ButtonAction

from .forms import EventForm
from .ics import event_ics
from .models import Event

if TYPE_CHECKING:
    from abilian.core.models.subjects import User

blueprint = CommunityBlueprint(
    "calendar", __name__, url_prefix="/calendar", template_folder="templates"
)
route = blueprint.route
blueprint.before_request(in_community("event_id", Event))
blueprint.before_request(with_tool("has_calendar"))

#: How many of the events to come an event's page shows beside it.
OTHERS = 4


@route("/")
def index() -> str:
    """The events to come, soonest first."""
    events = _events().filter(Event.end > datetime.now()).order_by(Event.start)
    return _calendar(events.all(), past=False)


@route("/archives/")
def archives() -> str:
    """The events past, latest first."""
    events = _events().filter(Event.end <= datetime.now())
    return _calendar(events.order_by(Event.start.desc()).all(), past=True)


def _events():
    """The community's events, and no other community's."""
    return Event.query.filter(Event.community_id == g.community.id)


def _calendar(events: list[Event], past: bool) -> str:
    by_month = groupby(lambda e: date(e.start.year, e.start.month, 1), events)
    months = sorted(by_month.items(), reverse=past)
    shown = _month_shown()
    return render_template(
        "calendar/index.html",
        months=months,
        past=past,
        month=shown,
        today=datetime.now().date(),
        weeks=month_weeks(shown, _events_in_grid(shown)),
        previous=_shift(shown, -1),
        following=_shift(shown, 1),
    )


def _events_in_grid(month: date) -> list[Event]:
    """The events that start on a day the grid of `month` shows, and no others."""
    weeks = calendar.Calendar().monthdatescalendar(month.year, month.month)
    first = datetime.combine(weeks[0][0], datetime.min.time())
    after = datetime.combine(weeks[-1][-1], datetime.min.time()) + timedelta(days=1)
    return _events().filter(Event.start >= first, Event.start < after).all()


def _month_shown() -> date:
    """The month beside the list: `?month=2026-11`, or this month."""
    asked = request.args.get("month")
    if not asked:
        return datetime.now().date().replace(day=1)
    try:
        return datetime.strptime(asked, "%Y-%m").date()
    except ValueError as e:
        msg = f"Not a month: {asked!r}"
        raise BadRequest(msg) from e


def _shift(month: date, by: int) -> date:
    index = month.year * 12 + month.month - 1 + by
    return date(index // 12, index % 12 + 1, 1)


def can_change(user: User, event: Event) -> bool:
    """May `user` change or delete `event`? Who posted it, or the community's
    managers."""
    return event.creator == user or can_manage(user, event.community)


def month_weeks(month: date, events: list[Event]) -> list[list[tuple[date, list]]]:
    """The weeks of `month`, Monday first, each day with the events that start on
    it; days of the months around it fill the first and last weeks."""
    by_day = groupby(lambda e: e.start.date(), events)
    weeks = calendar.Calendar().monthdatescalendar(month.year, month.month)
    return [[(day, by_day.get(day, [])) for day in week] for week in weeks]


class BaseEventView:
    Model = Event
    Form = EventForm
    pk = "event_id"

    def index_url(self):
        return url_for(".index", community_id=g.community.slug)

    def view_url(self):
        return url_for(self.obj)


class EventView(BaseEventView, views.ObjectView[Event, EventForm]):
    """An event's page."""

    methods = ["GET", "HEAD"]
    Form = EventForm
    template = "calendar/event.html"

    @property
    def template_kwargs(self):
        kw = super().template_kwargs
        kw["event"] = self.obj
        kw["may_change"] = can_change(authenticated_user(), self.obj)
        kw["others"] = (
            _events()
            .filter(Event.end > datetime.now(), Event.id != self.obj.id)
            .order_by(Event.start)
            .limit(OTHERS)
            .all()
        )
        return kw


event_view = EventView.as_view("event")
views.default_view(blueprint, Event, "event_id", kw_func=default_view_kw)(event_view)
route("/<int:event_id>/")(event_view)


@route("/<int:event_id>/event.ics")
def event_file(event_id: int) -> Response:
    """The event as a file one's own calendar takes in."""
    event = _events().filter(Event.id == event_id).first_or_404()
    body = event_ics(event, url_for(event, _external=True), request.host, utcnow())
    return Response(
        body,
        mimetype="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="event-{event.id}.ics"'},
    )


class EventCreateView(BaseEventView, views.ObjectCreate[Event, EventForm]):
    template = "calendar/event_form.html"
    _message_success = _l("The event is posted.")
    POST_BUTTON = ButtonAction(
        "form", "create", btn_class="primary", title=_l("Post this event")
    )

    title = _l("New event")

    def after_populate_obj(self) -> None:
        if self.obj.community is None:
            self.obj.community = g.community._model

    def get_form_buttons(self, *args, **kwargs):
        return [self.POST_BUTTON, views.object.CANCEL_BUTTON]

    @property
    def activity_target(self):
        return self.obj.community


event_create_view = EventCreateView.as_view("new_event", view_endpoint=".event")
route("/new_event/")(event_create_view)


class ChangingAnEvent(BaseEventView):
    """What changes an event, or deletes it: refused unless `can_change`."""

    def init_object(self, args, kwargs):
        args, kwargs = super().init_object(args, kwargs)
        if not can_change(authenticated_user(), self.obj):
            raise Forbidden
        return args, kwargs


class EventEditView(ChangingAnEvent, views.ObjectEdit[Event, EventForm]):
    template = "calendar/event_form.html"
    _message_success = _l("The event is changed.")
    POST_BUTTON = ButtonAction(
        "form", "create", btn_class="primary", title=_l("Post this event")
    )

    title = _l("Edit event")


event_edit_view = EventEditView.as_view("event_edit", view_endpoint=".event")
route("/<int:event_id>/edit")(event_edit_view)


class EventDelete(ChangingAnEvent, views.ObjectDelete[Event, EventForm]):
    _message_success = _l("The event is deleted.")

    @property
    def activity_target(self):
        return self.obj.community


route("/<int:event_id>/delete")(EventDelete.as_view("event_delete"))
