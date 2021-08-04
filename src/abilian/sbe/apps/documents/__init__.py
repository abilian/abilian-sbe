"""Folders / Documents module."""
from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from abilian.sbe.app import Application


def register_plugin(app: "Application"):
    from . import signals  # noqa
    from . import lock
    from .cli import antivirus
    from .models import setup_listener
    from .views import blueprint

    app.register_blueprint(blueprint)
    setup_listener()

    # set default lock lifetime
    app.config.setdefault("SBE_LOCK_LIFETIME", lock.DEFAULT_LIFETIME)

    app.cli.add_command(antivirus)
