"""Create an application instance."""
import click
from flask.cli import AppGroup

import abilian.cli
from abilian.sbe.app import create_app


def register_commands(app):
    for obj in vars(abilian.cli).values():
        if isinstance(obj, (click.core.Command, AppGroup)):
            app.cli.add_command(obj)


app = create_app()

register_commands(app)
