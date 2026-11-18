# Copyright (c) 2012-2024, Abilian SAS

"""Calendar module."""

from __future__ import annotations


def register_plugin(app) -> None:
    from .views import blueprint

    app.register_blueprint(blueprint)
