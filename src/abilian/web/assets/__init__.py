# Copyright (c) 2012-2024, Abilian SAS

"""Static resources served directly, outside the Vite build.

The flask-assets / LESS / Closure bundling pipeline this module used to own has
been replaced by Vite. What remains is the URL that serves `web/resources/`:
the icon font, highlight.js for the JSON debug view, and the images.
"""

from __future__ import annotations

import typing
from importlib import resources as rso

from abilian.services.security import ANONYMOUS

if typing.TYPE_CHECKING:
    from abilian.app import Application

RESOURCES_DIR = str(rso.files("abilian.web") / "resources")


def init_app(app: Application) -> None:
    app.add_static_url(
        "abilian", RESOURCES_DIR, endpoint="abilian_static", roles=ANONYMOUS
    )
