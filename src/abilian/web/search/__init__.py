# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.core.signals import register_js_api
from abilian.web import url_for

if TYPE_CHECKING:
    from abilian.app import Application


# __all__ = ["BaseCriterion", "TextSearchCriterion"]


def _do_register_js_api(sender: Application) -> None:
    app = sender
    js_api = app.js_api.setdefault("search", {})
    js_api["live"] = url_for("search.live")


def register_plugin(app: Application) -> None:
    from .views import search

    app.register_blueprint(search)
    register_js_api.connect(_do_register_js_api)
