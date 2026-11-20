# Copyright (c) 2012-2026, Abilian SAS

"""A community's calendar: its own events, to come or past; an event; making one;
the month at a glance."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from html import unescape
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
import pytz
from flask import g
from werkzeug.datastructures import MultiDict

from abilian.sbe.apps.calendar.forms import EventForm
from abilian.sbe.apps.calendar.models import Event, EventAttachment
from abilian.sbe.apps.calendar.views import _events_in_grid, month_weeks
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.models.subjects import User
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _event(community: Community, title: str, days: int, **kw: str) -> Event:
    start = datetime.now().replace(microsecond=0) + timedelta(days=days)
    return Event(
        title=title,
        community=community,
        start=start,
        end=start + timedelta(hours=2),
        description="<p>What it is.</p>",
        **kw,
    )


@pytest.fixture
def member(community1: Community, db: SQLAlchemy) -> User:
    ensure_services_started(["security"])
    community1.set_membership(community1.test_user, MEMBER)
    db.session.commit()
    return community1.test_user


@pytest.fixture
def events(
    community1: Community, community2: Community, member: User, db: SQLAlchemy
) -> dict[str, Event]:
    events = {
        "coming": _event(community1, "General meeting", 10, location="Room 2"),
        "past": _event(community1, "Last year's party", -30),
        "elsewhere": _event(community2, "Someone else's meeting", 10),
    }
    db.session.add_all(events.values())
    db.session.commit()
    return events


def _page(client: FlaskClient, user: User, url: str) -> str:
    with client_login(client, user):
        response = client.get(url)
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


def test_the_calendar_lists_its_own_events_to_come(
    client: FlaskClient, community1: Community, member: User, events: dict
) -> None:
    html = _page(
        client, member, url_for("calendar.index", community_id=community1.slug)
    )

    assert "General meeting" in html
    assert "Room 2" in html
    assert "Last year's party" not in html
    assert "Someone else's meeting" not in html


def test_the_past_events_are_apart(
    client: FlaskClient, community1: Community, member: User, events: dict
) -> None:
    url = url_for("calendar.archives", community_id=community1.slug)
    # The list, not the month beside it, which shows what is to come too.
    html = _page(client, member, url)
    listed = html.split('aria-labelledby="events"')[1].split("</section>")[0]

    assert "Last year's party" in listed
    assert "General meeting" not in listed


def test_an_event_links_only_to_the_web(
    client: FlaskClient, member: User, events: dict, db: SQLAlchemy
) -> None:
    event = events["coming"]
    event.url = "javascript:alert(1)"
    db.session.commit()

    html = _page(client, member, url_for(event))

    assert "What it is." in html
    assert 'href="javascript:' not in html


def test_an_event_is_made_in_its_community(
    client: FlaskClient, community1: Community, member: User, db: SQLAlchemy
) -> None:
    # Away from UTC, so that a time shifted as if it were UTC would show.
    member.timezone = pytz.timezone("Europe/Paris")
    db.session.commit()
    day = (datetime.now().date() + timedelta(days=3)).isoformat()
    data = MultiDict(
        [
            ("title", "Board meeting"),
            ("start", day),
            ("start", "09:00"),
            ("end", day),
            ("end", "11:00"),
            ("description", "<p>The board.</p>"),
            ("__action", "create"),
        ]
    )
    with client_login(client, member):
        response = client.post(
            url_for("calendar.new_event", community_id=community1.slug), data=data
        )

    assert response.status_code == 302, response.get_data(as_text=True)[:500]
    event = Event.query.filter(Event.title == "Board meeting").one()
    assert event.community_id == community1.id
    assert event.start.hour == 9
    # Shown at the hour it was given: kept as a local time, not shifted as UTC.
    html = _page(client, member, url_for(event))
    assert "9:00" in html
    assert "10:00" not in html


def test_the_month_starts_on_a_monday_and_marks_the_days_of_events() -> None:
    event = Event(
        title="On the 18th",
        start=datetime(2026, 11, 18, 9),
        end=datetime(2026, 11, 18, 11),
    )

    weeks = month_weeks(date(2026, 11, 1), [event])

    assert all(len(week) == 7 for week in weeks)
    assert weeks[0][0][0].weekday() == 0
    days = {day: todays for week in weeks for day, todays in week}
    assert days[date(2026, 11, 18)] == [event]
    assert days[date(2026, 11, 17)] == []


def test_event_description_is_sanitized(test_request_context) -> None:
    html = '<p style="text-align: center; color: red">Hi</p><script>alert("x")</script>'
    form = EventForm(MultiDict({"description": html}))
    form.validate_description(form.description)

    assert form.description.data == ('<p style="text-align: center;">Hi</p>alert("x")')


def test_an_event_goes_to_ones_own_calendar(
    client: FlaskClient, community1: Community, member: User, events: dict
) -> None:
    event = events["coming"]
    with client_login(client, member):
        response = client.get(
            url_for(
                "calendar.event_file", community_id=community1.slug, event_id=event.id
            )
        )

    assert response.mimetype == "text/calendar"
    assert "attachment" in response.headers["Content-Disposition"]
    body = response.get_data(as_text=True)
    assert f"DTSTART:{event.start:%Y%m%dT%H%M%S}\r\n" in body
    assert "SUMMARY:General meeting\r\n" in body
    assert "LOCATION:Room 2\r\n" in body
    assert "DESCRIPTION:What it is.\r\n" in body


def test_who_posted_an_event_deletes_it(
    client: FlaskClient,
    community1: Community,
    member: User,
    events: dict,
    db: SQLAlchemy,
) -> None:
    event = events["coming"]
    event.creator = member
    db.session.commit()
    url = url_for("calendar.event", community_id=community1.slug, event_id=event.id)

    assert 'id="modal-delete"' in _page(client, member, url)
    with client_login(client, member):
        response = client.post(
            url_for(
                "calendar.event_delete", community_id=community1.slug, event_id=event.id
            ),
            data={"__action": "delete"},
        )

    assert response.status_code == 302
    assert db.session.get(Event, event.id) is None


def test_another_member_neither_changes_nor_deletes_an_event(
    client: FlaskClient,
    community1: Community,
    member: User,
    events: dict,
    db: SQLAlchemy,
) -> None:
    event = events["coming"]
    here = {"community_id": community1.slug, "event_id": event.id}
    edit_url = url_for("calendar.event_edit", **here)

    html = _page(client, member, url_for("calendar.event", **here))
    assert 'id="modal-delete"' not in html
    assert edit_url not in html
    with client_login(client, member):
        edit = client.get(edit_url)
        delete = client.post(
            url_for("calendar.event_delete", **here), data={"__action": "delete"}
        )

    assert (edit.status_code, delete.status_code) == (403, 403)
    assert db.session.get(Event, event.id) is not None


def test_a_manager_changes_any_event(
    client: FlaskClient,
    community1: Community,
    member: User,
    events: dict,
    db: SQLAlchemy,
) -> None:
    community1.set_membership(member, MANAGER)
    db.session.commit()
    here = {"community_id": community1.slug, "event_id": events["coming"].id}

    html = _page(client, member, url_for("calendar.event", **here))

    assert url_for("calendar.event_edit", **here) in html
    assert 'id="modal-delete"' in html


def test_any_member_copies_an_events_link(
    client: FlaskClient, community1: Community, member: User, events: dict
) -> None:
    here = {"community_id": community1.slug, "event_id": events["coming"].id}

    html = _page(client, member, url_for("calendar.event", **here))

    link = url_for("calendar.event", _external=True, **here)
    assert f'data-copy="{link}"' in html


def test_the_month_grid_loads_only_its_own_days_events(
    app, db: SQLAlchemy, community1: Community
) -> None:
    starts = {
        "grid's first day": datetime(2026, 10, 26, 9),
        "in the month": datetime(2026, 11, 18, 9),
        "months before": datetime(2026, 3, 1, 9),
        "after the grid": datetime(2026, 12, 7, 9),
    }
    for title, start in starts.items():
        db.session.add(
            Event(
                title=title,
                community=community1,
                start=start,
                end=start + timedelta(hours=2),
            )
        )
    db.session.commit()

    with app.test_request_context():
        g.community = community1
        loaded = {e.title for e in _events_in_grid(date(2026, 11, 1))}

    assert loaded == {"grid's first day", "in the month"}


def test_today_is_said_in_the_month(
    client: FlaskClient, community1: Community, member: User
) -> None:
    html = _page(
        client, member, url_for("calendar.index", community_id=community1.slug)
    )

    assert html.count('aria-current="date"') == 1


def test_an_event_comes_with_its_files_and_lets_them_go(
    client: FlaskClient, community1: Community, member: User, db: SQLAlchemy
) -> None:
    """Attached and removed from its form, as a wiki page's; read from its page."""
    day = (datetime.now().date() + timedelta(days=3)).isoformat()
    data = MultiDict(
        [
            ("title", "Board meeting"),
            ("start", day),
            ("start", "09:00"),
            ("end", day),
            ("end", "11:00"),
            ("description", "<p>The board.</p>"),
            ("attachments", (BytesIO(b"the agenda"), "agenda.txt")),
            ("__action", "create"),
        ]
    )
    with client_login(client, member):
        client.post(
            url_for("calendar.new_event", community_id=community1.slug), data=data
        )
    event = Event.query.filter(Event.title == "Board meeting").one()
    (agenda,) = event.attachments
    here = {"community_id": community1.slug, "event_id": event.id}
    download = url_for("calendar.event_attachment", attachment_id=agenda.id, **here)

    page = _page(client, member, url_for(event))
    with client_login(client, member):
        content = client.get(download).get_data()
        client.post(
            url_for("calendar.event_edit", **here),
            data=MultiDict(
                [
                    *[
                        (k, v)
                        for k, v in data.items(multi=True)
                        if k not in {"attachments", "__action"}
                    ],
                    ("remove_attachment", str(agenda.id)),
                    ("__action", "edit"),
                ]
            ),
        )

    assert f'href="{download}"' in page
    assert content == b"the agenda"
    db.session.expire_all()
    assert event.attachments == []


def test_an_events_file_is_found_under_its_event_only(
    client: FlaskClient, events: dict[str, Event], member: User, db: SQLAlchemy
) -> None:
    coming, past = events["coming"], events["past"]
    attachment = EventAttachment(name="secret.txt")
    past.attachments.append(attachment)
    attachment.set_content(b"secret", "text/plain")
    db.session.commit()

    with client_login(client, member):
        response = client.get(
            url_for(
                "calendar.event_attachment",
                community_id=coming.community.slug,
                event_id=coming.id,
                attachment_id=attachment.id,
            )
        )

    assert response.status_code == 404


def test_an_event_is_discussed_in_a_thread_started_from_it(
    client: FlaskClient, events: dict[str, Event], member: User, db: SQLAlchemy
) -> None:
    event = events["coming"]
    community = event.community
    page = _page(client, member, url_for(event))
    start = url_for("forum.new_thread", community_id=community.slug, event=event.id)
    form = _page(client, member, start)

    with client_login(client, member):
        client.post(
            url_for("forum.new_thread", community_id=community.slug),
            data={
                "title": "General meeting",
                "message": "<p>Who brings the coffee?</p>",
                "event": str(event.id),
                "__action": "create",
            },
        )
    db.session.expire_all()

    assert f'href="{start}"' in page
    assert 'value="General meeting"' in form
    assert f'name="event" value="{event.id}"' in form
    assert event.thread is not None
    assert event.thread.title == "General meeting"
    assert "Discussed in" in _page(client, member, url_for(event))
