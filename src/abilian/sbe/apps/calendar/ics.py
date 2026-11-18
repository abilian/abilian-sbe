# Copyright (c) 2012-2026, Abilian SAS

"""An event as an iCalendar file (RFC 5545), to add it to one's own calendar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from markupsafe import Markup

if TYPE_CHECKING:
    from datetime import datetime

    from .models import Event

#: How long a content line may be, in octets, before it folds (RFC 5545, 3.1).
LINE_OCTETS = 75


def event_ics(event: Event, page_url: str, host: str, now: datetime) -> str:
    """`event` as a calendar holding it alone. Its moments are local times kept
    without a zone, so they go as floating times: each calendar reads them in its
    own zone, as the community does. `now` is in UTC."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Abilian//SBE//EN",
        "BEGIN:VEVENT",
        f"UID:event-{event.id}@{host}",
        f"DTSTAMP:{now:%Y%m%dT%H%M%S}Z",
        f"DTSTART:{event.start:%Y%m%dT%H%M%S}",
    ]
    if event.end:
        lines.append(f"DTEND:{event.end:%Y%m%dT%H%M%S}")
    lines.append(f"SUMMARY:{_text(event.title)}")
    if event.location:
        lines.append(f"LOCATION:{_text(event.location)}")
    if event.description:
        lines.append(f"DESCRIPTION:{_text(Markup(event.description).striptags())}")
    lines += [f"URL:{page_url}", "END:VEVENT", "END:VCALENDAR"]
    return "".join(_fold(line) + "\r\n" for line in lines)


def _text(value: str) -> str:
    """A TEXT value, escaped (RFC 5545, 3.3.11)."""
    for char, escaped in (("\\", "\\\\"), (";", "\\;"), (",", "\\,")):
        value = value.replace(char, escaped)
    return value.replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> str:
    """`line` cut into lines of at most 75 octets, each after the first starting
    with a space; never inside a character."""
    parts, part = [], ""
    for char in line:
        limit = LINE_OCTETS if not parts else LINE_OCTETS - 1
        if len((part + char).encode()) > limit:
            parts.append(part)
            part = ""
        part += char
    return "\r\n ".join([*parts, part])
