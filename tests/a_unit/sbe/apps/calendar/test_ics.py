# Copyright (c) 2012-2026, Abilian SAS

"""An event as an iCalendar file: its text escaped, its long lines folded."""

from __future__ import annotations

from datetime import datetime

from abilian.sbe.apps.calendar.ics import LINE_OCTETS, event_ics
from abilian.sbe.apps.calendar.models import Event


def test_an_event_as_a_calendar_file() -> None:
    event = Event(
        title="Bureau; vote, budget",
        location="Salle 2\nPremier étage",
        description="<p>Ordre du jour : " + "é" * 60 + "</p>",
        start=datetime(2026, 11, 24, 18, 0),
        end=datetime(2026, 11, 24, 20, 0),
    )
    event.id = 7

    ics = event_ics(
        event, "https://x.example/e/7/", "x.example", datetime(2026, 11, 18, 9, 30)
    )
    lines = ics.split("\r\n")

    assert ics.endswith("END:VCALENDAR\r\n")
    assert "UID:event-7@x.example" in lines
    assert "DTSTAMP:20261118T093000Z" in lines
    assert "DTSTART:20261124T180000" in lines
    assert "DTEND:20261124T200000" in lines
    assert r"SUMMARY:Bureau\; vote\, budget" in lines
    assert r"LOCATION:Salle 2\nPremier étage" in lines
    assert all(len(line.encode()) <= LINE_OCTETS for line in lines)
    unfolded = ics.replace("\r\n ", "")
    assert "DESCRIPTION:Ordre du jour : " + "é" * 60 + "\r\n" in unfolded
