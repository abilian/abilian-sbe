# Copyright (c) 2012-2024, Abilian SAS

"""Creating a community makes you a manager of it -- as a membership.

It used to be a clause in a predicate: `is_manager` granted to
`community.creator`, and `can_manage` -- which is what the route guard
enforces -- did not. So a creator who was not also a site admin was offered the
manage actions and refused by the views behind them, and "who manages this
community" could not be read off the member list or revoked through it.

Recording it as a membership makes the grant ordinary data: visible in the
members table, revocable there, and answerable by the same question as
everyone else's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import url_for

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, Community
from abilian.sbe.apps.communities.security import can_manage
from abilian.services import security_service
from abilian.services.security import ADMIN
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy

FORM = {
    "name": "Brand New",
    "description": "A community made by a test",
    "type": "informative",
    "linked_group": "",
    "__action": "create",
}


def test_the_creator_becomes_a_manager_member(
    app: Application, db: SQLAlchemy, client: FlaskClient
) -> None:
    ensure_services_started(["security"])
    admin = User(email="admin@example.com", password="test", can_login=True)  # noqa: S106
    db.session.add(admin)
    db.session.flush()
    security_service.grant_role(admin, ADMIN)
    db.session.flush()

    with client_login(client, admin):
        response = client.post(url_for("communities.new"), data=FORM)

    assert response.status_code in (200, 302)
    community = Community.query.filter(Community.name == FORM["name"]).one()

    assert community.creator == admin
    assert community.get_role(admin) == MANAGER, (
        "the creator is not in the member list, so nothing but a special case "
        "in a predicate could have said they manage it"
    )
    assert can_manage(community, admin)
