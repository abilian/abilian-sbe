# Copyright (c) 2012-2024, Abilian SAS

"""One-off data migrations that need the model layer.

Alembic can only write rows. A membership is more than a row: it carries a
count on the community and a role assignment on the community's folder, both
written by `set_membership` and the signal behind it. So these live here.
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext
from flask_super.cli import command

from abilian.core.extensions import db
from abilian.sbe.apps.communities.models import MANAGER, Community
from abilian.sbe.apps.communities.roles import set_exclusive_role
from abilian.services.security import security


@command()
@click.option("--dry-run", is_flag=True, help="List what would change, change nothing.")
@with_appcontext
def backfill_creator_memberships(dry_run: bool) -> None:
    """Make every community's creator a MANAGER member of it.

    Managing a community used to be granted to its creator by a clause in a
    predicate, invisible to the member list and impossible to revoke there.
    The clause is gone; this writes the grant it stood for as data. Creators
    who are already members keep the role they have -- a role someone chose
    deliberately, possibly to demote them, must win over this backfill.
    """
    for community in Community.query.filter(Community.creator_id.isnot(None)):
        if community.get_role(community.creator) is not None:
            continue
        click.echo(f"{community.name}: {community.creator.email} -> manager")
        if not dry_run:
            community.set_membership(community.creator, MANAGER)

    if dry_run:
        click.echo("dry run, nothing written")
    else:
        db.session.commit()


@command()
@click.option("--dry-run", is_flag=True, help="List what would change, change nothing.")
@with_appcontext
def backfill_community_roles(dry_run: bool) -> None:
    """Record every existing membership as a role on its community.

    Memberships used to be projected onto the community's *folder* only, which
    left the community itself unanswerable: `has_permission(user, MANAGE,
    community)` was False for its own manager. New memberships are recorded on
    the community by a signal handler; this does the same for the ones that
    already exist.

    Idempotent -- `set_exclusive_role` grants only what is missing -- so it is
    safe to re-run, and safe to run before or after
    `backfill-creator-memberships`.
    """
    missing = 0
    for community in Community.query:
        for membership in community.memberships:
            held = security.get_roles(membership.user, community, no_group_roles=True)
            if membership.role in held:
                continue
            missing += 1
            click.echo(
                f"{community.name}: {membership.user.email} -> {membership.role}"
            )
            if not dry_run:
                set_exclusive_role(membership.user, membership.role, community)

    if dry_run:
        click.echo(f"dry run, nothing written ({missing} memberships)")
    else:
        db.session.commit()
        click.echo(f"{missing} memberships recorded on their community")
