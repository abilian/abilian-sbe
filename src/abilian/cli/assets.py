# Copyright (c) 2012-2024, Abilian SAS

"""Deprecated `flask assets` commands, kept so existing deployments keep booting.

The flask-assets/LESS/Closure pipeline is gone; assets are built by Vite
(`make front`) and ship inside the wheel. But `flask assets build` is baked into
deployment recipes we cannot retroactively edit -- notably the SlapOS instance
template, where it runs as a *supervised service*, so a failing command becomes
a restart loop rather than a one-off error.

flask-assets is still installed as a transitive dependency and registers its own
`assets` group, which now raises AttributeError because nothing initialises its
environment. These commands shadow it with a no-op that says what to run instead.

Remove once no deployment invokes `flask assets` any more.
"""

from __future__ import annotations

import click
from flask_super.cli import group

REPLACEMENT = (
    "Assets are built by Vite now: run `make front` (or `npm run build` in vite/)."
)


@group()
def assets() -> None:
    """Deprecated: superseded by the Vite build."""


@assets.command()
def build() -> None:
    """No-op. Kept so deployment recipes that call it keep working."""
    click.echo(f"`flask assets build` does nothing. {REPLACEMENT}")


@assets.command()
def clean() -> None:
    """No-op. Kept so deployment recipes that call it keep working."""
    click.echo(f"`flask assets clean` does nothing. {REPLACEMENT}")
