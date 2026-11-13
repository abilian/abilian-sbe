# Copyright (c) 2012-2024, Abilian SAS

"""Who may add members to a community.

Every step of the member wizard is a manager action -- it ends by writing
memberships with arbitrary roles -- but the routes carried only the community
blueprint's `check_access`, which asks for *membership*, not management. So any
member of a community could post to the final step and promote themselves:

    POST /communities/<slug>/members/wizard/complete
    existing_account={"their-own@email": "manager"}

and a reader became a manager of that community, which carries MANAGE over all
of its content. `@csrf.protect` is no barrier -- a logged-in member has a token
on every page they are legitimately served.

The sibling endpoint `members_post`, which edits one role, has always had
`@can_manage`; the wizard, which writes any number of them, did not.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from flask import url_for

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, READER
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community

#: Every step, not just the one that writes: the earlier steps disclose the
#: member list and drive account creation.
WIZARD_STEPS = [
    "communities.wizard_data_insertion",
    "communities.wizard_check_data",
    "communities.wizard_new_accounts",
]


def _member(db: SQLAlchemy, community: Community, email: str, role) -> User:
    user = User(email=email, password="test", can_login=True)  # noqa: S106
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    db.session.flush()
    return user


@pytest.mark.parametrize("endpoint", WIZARD_STEPS)
def test_a_plain_member_cannot_open_the_wizard(
    endpoint: str,
    community1: Community,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    ensure_services_started(["security"])
    reader = _member(db, community1, "reader@example.com", READER)

    with client_login(client, reader):
        response = client.get(url_for(endpoint, community_id=community1.slug))

    assert response.status_code == 403


def test_a_plain_member_cannot_promote_themselves(
    community1: Community, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    """The escalation itself."""
    ensure_services_started(["security"])
    reader = _member(db, community1, "reader@example.com", READER)

    with client_login(client, reader):
        response = client.post(
            url_for("communities.wizard_saving", community_id=community1.slug),
            data={"existing_account": json.dumps({reader.email: "manager"})},
        )

    db.session.expire_all()
    assert response.status_code == 403
    assert community1.get_role(reader) == READER


def test_a_manager_still_can(
    community1: Community, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    """The fix must not take the feature away from the people it is for."""
    ensure_services_started(["security"])
    manager = _member(db, community1, "manager@example.com", MANAGER)
    outsider = User(email="outsider@example.com", password="test", can_login=True)  # noqa: S106
    db.session.add(outsider)
    db.session.flush()

    with client_login(client, manager):
        response = client.post(
            url_for("communities.wizard_saving", community_id=community1.slug),
            data={"existing_account": json.dumps({outsider.email: "member"})},
        )

    db.session.expire_all()
    assert response.status_code == 302, "the wizard redirects on success"
    assert community1.get_role(outsider) is not None, "the member was not added"
