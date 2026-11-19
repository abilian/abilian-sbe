# Copyright (c) 2012-2026, Abilian SAS

"""Helpers for the pages on the Abilian Design System (ADS).

`notes/ux/design-principles.md` says what these pages look like; the static mockups in
`mockups/` use the same helpers, so the two cannot drift apart.
"""

from __future__ import annotations

import json
import zlib
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from markupsafe import Markup

if TYPE_CHECKING:
    from flask import Flask

#: Tabler's icons (MIT), the subset `mockups/extract_icons.py` writes.
ICONS = Path(__file__).parent / "static" / "icons.json"

#: The identity palette in `static/theme.css`: `--sbe-id-1` to `--sbe-id-8`.
ID_COLOURS = 8


@cache
def _icons() -> dict[str, str]:
    return json.loads(ICONS.read_text())


def icon(name: str, classes: str = "ads-icon") -> Markup:
    """An icon, decorative: whatever carries it says what it means.

    An unknown name raises `KeyError`, so a misspelt or missing icon fails at
    render time rather than leaving a hole in the page.
    """
    attributes = f'class="{classes}" aria-hidden="true" focusable="false"'
    return Markup(_icons()[name].replace("CLASS_SLOT", attributes))


#: A file's icon and colour by its extension, the colours office suites use: what a
#: reader recognises before reading the name (`.sbe-filetype--*` in `theme.css`).
FILE_TYPES = {
    "pdf": ("file-type-pdf", "pdf"),
    "odt": ("file-type-doc", "text"),
    "doc": ("file-type-doc", "text"),
    "docx": ("file-type-doc", "text"),
    "ods": ("file-type-xls", "sheet"),
    "xls": ("file-type-xls", "sheet"),
    "xlsx": ("file-type-xls", "sheet"),
    "odp": ("file-type-ppt", "slides"),
    "ppt": ("file-type-ppt", "slides"),
    "pptx": ("file-type-ppt", "slides"),
    "png": ("photo", "image"),
    "jpg": ("photo", "image"),
    "jpeg": ("photo", "image"),
    "gif": ("photo", "image"),
    "svg": ("photo", "image"),
    "zip": ("file-type-zip", ""),
}
UNKNOWN_FILE = ("file", "")


def file_icon(name: str) -> Markup:
    """A file's icon, in its type's colour, from its name's extension."""
    glyph, colour = FILE_TYPES.get(name.rsplit(".", 1)[-1].lower(), UNKNOWN_FILE)
    modifier = f" sbe-filetype--{colour}" if colour else ""
    return Markup('<span class="sbe-filetype{}">{}</span>').format(
        modifier, icon(glyph)
    )


def folder_icon() -> Markup:
    return Markup('<span class="sbe-filetype sbe-filetype--folder">{}</span>').format(
        icon("folder")
    )


def identity_class(key: str | int) -> str:
    """One of the eight identity colours, stable for a key.

    A person's comes from their name; a community's from its id, so that
    communities created one after the other differ.
    """
    n = key if isinstance(key, int) else zlib.crc32(key.encode())
    return f"sbe-id-{n % ID_COLOURS + 1}"


def initials(name: str) -> str:
    """Up to two letters for an avatar or a tile: "Claire Moreau" is "CM"."""
    words = name.split()
    return "".join(word[0] for word in words[:2]).upper() or "?"


def register(app: Flask) -> None:
    """Make the helpers available to every template, with the user's communities,
    which the bar lists on every page."""
    # Here rather than at the top: the mockups import this module without the models.
    from abilian.sbe.apps.communities.models import (
        communities_of,
        community_counts,
        site_figures,
    )
    from abilian.sbe.apps.main.recent import recently_opened

    for helper in (
        icon,
        file_icon,
        folder_icon,
        identity_class,
        initials,
        communities_of,
        community_counts,
        site_figures,
        recently_opened,
    ):
        app.add_template_global(helper)
