"""Forum views."""
from datetime import date, datetime

from flask import g, render_template
from toolz import groupby

from abilian.i18n import _l
from abilian.web import url_for, views
from abilian.web.action import ButtonAction

from ..communities.blueprint import Blueprint
from ..communities.views import default_view_kw
from .forms import EventForm
from .models import Event

blueprint = Blueprint(
    "calendar", __name__, url_prefix="/calendar", template_folder="templates"
)
route = blueprint.route


@route("/")
def index():
    events = Event.query.filter(Event.end > datetime.now()).order_by(Event.start).all()

    def get_month(event):
        year = event.start.year
        month = event.start.month
        return date(year, month, 1)

    groups = sorted(groupby(get_month, events).items())
    ctx = {"groups": groups}
    return render_template("calendar/index.html", **ctx)


@route("/archives/")
def archives():
    events = (
        Event.query.filter(Event.end <= datetime.now())
        .order_by(Event.start.desc())
        .all()
    )

    def get_month(event):
        year = event.start.year
        month = event.start.month
        return date(year, month, 1)

    groups = sorted(groupby(get_month, events).items(), reverse=True)
    ctx = {"groups": groups}
    return render_template("calendar/archives.html", **ctx)


class BaseEventView:
    Model = Event
    Form = EventForm
    pk = "event_id"
    base_template = "community/_base.html"

    def index_url(self):
        return url_for(".index", community_id=g.community.slug)

    def view_url(self):
        return url_for(self.obj)


class EventView(BaseEventView, views.ObjectView):
    methods = ["GET", "HEAD"]
    Form = EventForm
    template = "calendar/event.html"

    @property
    def template_kwargs(self):
        kw = super().template_kwargs
        kw["event"] = self.obj
        return kw


event_view = EventView.as_view("event")
views.default_view(blueprint, Event, "event_id", kw_func=default_view_kw)(event_view)
route("/<int:event_id>/")(event_view)


class EventCreateView(BaseEventView, views.ObjectCreate):
    POST_BUTTON = ButtonAction(
        "form", "create", btn_class="primary", title=_l("Post this event")
    )

    title = _l("New event")

    def after_populate_obj(self):
        if self.obj.community is None:
            self.obj.community = g.community._model

    def get_form_buttons(self, *args, **kwargs):
        return [self.POST_BUTTON, views.object.CANCEL_BUTTON]

    @property
    def activity_target(self):
        return self.obj.community


event_create_view = EventCreateView.as_view("new_event", view_endpoint=".event")
route("/new_event/")(event_create_view)


class EventEditView(BaseEventView, views.ObjectEdit):
    POST_BUTTON = ButtonAction(
        "form", "create", btn_class="primary", title=_l("Post this event")
    )

    title = _l("Edit event")


event_edit_view = EventEditView.as_view("event_edit", view_endpoint=".event")
route("/<int:event_id>/edit")(event_edit_view)
