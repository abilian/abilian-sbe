# coding=utf-8
"""Folders / Documents module."""
import typing

if typing.TYPE_CHECKING:
    from abilian.sbe.app import Application


def register_plugin(app: "Application") -> None:
    from .views import blueprint
    from .models import setup_listener
    from .cli import antivirus
    from . import signals  # noqa
    from . import lock

    app.register_blueprint(blueprint)
    setup_listener()

    # set default lock lifetime
    app.config.setdefault("SBE_LOCK_LIFETIME", lock.DEFAULT_LIFETIME)

    app.cli.add_command(antivirus)
