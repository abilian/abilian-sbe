# Copyright (c) 2012-2026, Abilian SAS

"""What is kept of the HTML people write in the rich text editor, or send by mail:
a forum message, an event's description."""

from __future__ import annotations

import bleach
from bleach.css_sanitizer import CSSSanitizer

ALLOWED_TAGS = frozenset(
    {
        "a",
        "abbr",
        "acronym",
        "b",
        "blockquote",
        "br",
        "code",
        "em",
        "i",
        "li",
        "ol",
        "strong",
        "ul",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "u",
        "img",
    }
)

ALLOWED_ATTRIBUTES = {
    "*": ["title"],
    "p": ["style"],
    "a": ["href", "title"],
    "abbr": ["title"],
    "acronym": ["title"],
    "img": ["src", "alt", "title"],
}

#: The editor aligns paragraphs: nothing else of their style is kept.
ALLOWED_STYLES = frozenset({"text-align"})


def sanitize_html(html: str) -> str:
    """`html` with only the allowed tags, attributes and styles: any other tag is
    dropped, its text kept."""
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        css_sanitizer=CSSSanitizer(allowed_css_properties=ALLOWED_STYLES),
        strip=True,
    )
