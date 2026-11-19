# Copyright (c) 2026, Abilian SAS

"""The communities to discover: open ones only, shown but not entered; joined at
once or on request, as their managers chose; a request answered from the members
page."""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from abilian.core.extensions import mail
from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import (
    CLOSED,
    MANAGER,
    MEMBER,
    ON_REQUEST,
    OPEN,
    Community,
    MembershipRequest,
)
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy


def _person(db: SQLAlchemy, name: str) -> User:
    user = User(
        first_name=name,
        last_name="Test",
        email=f"{name.lower()}@example.com",
        password=uuid4().hex,
        can_login=True,
    )
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture
def world(db: SQLAlchemy) -> dict:
    """A manager of three communities, one per way in, and an outsider."""
    ensure_services_started(["security"])
    manager, outsider = _person(db, "Mia"), _person(db, "Otto")
    communities = {}
    for visibility in (CLOSED, ON_REQUEST, OPEN):
        community = Community(name=f"Club {visibility}", visibility=visibility)
        db.session.add(community)
        db.session.flush()
        community.set_membership(manager, MANAGER)
        communities[visibility] = community
    db.session.commit()
    return {"manager": manager, "outsider": outsider, **communities}


def _discover(client: FlaskClient, user: User) -> str:
    with client_login(client, user):
        response = client.get(url_for("communities.discover"))
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


def _post(client: FlaskClient, user: User, community: Community, action: str):
    with client_login(client, user), mail.record_messages() as outbox:
        response = client.post(
            url_for("communities.discover"),
            data={"community": community.slug, "action": action},
        )
    return response, outbox


def test_only_the_open_communities_one_is_not_in_are_shown(
    client: FlaskClient, world: dict
) -> None:
    seen = _discover(client, world["outsider"])
    mine = _discover(client, world["manager"])

    assert "Club secret" not in seen
    assert "Club public" in seen
    assert "Club open" in seen
    assert "Managed by Mia Test" in seen
    assert 'value="ask"' in seen
    assert 'value="join"' in seen
    # Its managers' own communities are in the bar's menu, not among those to discover.
    assert "No other community is open for now." in mine


def test_an_open_community_is_joined_at_once(
    client: FlaskClient, world: dict, db: SQLAlchemy
) -> None:
    response, _outbox = _post(client, world["outsider"], world[OPEN], "join")

    assert response.status_code == 302
    assert response.location.endswith(url_for(world[OPEN]))
    assert world[OPEN].get_role(world["outsider"]) == MEMBER


@pytest.mark.parametrize(
    ("visibility", "action"),
    [(CLOSED, "join"), (CLOSED, "ask"), (ON_REQUEST, "join"), (OPEN, "ask")],
)
def test_a_community_is_entered_only_its_own_way(
    visibility: str, action: str, client: FlaskClient, world: dict
) -> None:
    response, _outbox = _post(client, world["outsider"], world[visibility], action)

    assert response.status_code == 400
    assert world[visibility].get_role(world["outsider"]) is None


def test_a_request_goes_to_the_managers_and_is_answered(
    client: FlaskClient, world: dict, db: SQLAlchemy
) -> None:
    community, outsider = world[ON_REQUEST], world["outsider"]

    response, outbox = _post(client, outsider, community, "ask")
    _post(client, outsider, community, "ask")
    page = _discover(client, outsider)
    (asking,) = MembershipRequest.query.filter_by(community_id=community.id).all()
    members = url_for("communities.members", community_id=community.slug)
    with client_login(client, world["manager"]):
        listed = client.get(members).get_data(as_text=True)
        with mail.record_messages() as told:
            client.post(
                url_for("communities.members_post", community_id=community.slug),
                data={"action": "accept-request", "request": str(asking.id)},
            )

    assert response.status_code == 302
    assert [message.recipients for message in outbox] == [["mia@example.com"]]
    assert "Otto Test asks to join Club public" in outbox[0].subject
    assert "Asked" in page
    assert 'value="accept-request"' in listed
    assert community.get_role(outsider) == MEMBER
    assert MembershipRequest.query.count() == 0
    assert [message.recipients for message in told] == [["otto@example.com"]]


def test_a_refused_request_leaves_its_person_out(
    client: FlaskClient, world: dict, db: SQLAlchemy
) -> None:
    community, outsider = world[ON_REQUEST], world["outsider"]
    db.session.add(MembershipRequest(community=community, user=outsider))
    db.session.commit()
    asking = MembershipRequest.query.one()

    with client_login(client, world["manager"]):
        client.post(
            url_for("communities.members_post", community_id=community.slug),
            data={"action": "refuse-request", "request": str(asking.id)},
        )

    assert community.get_role(outsider) is None
    assert MembershipRequest.query.count() == 0


def test_a_manager_opens_the_community_from_its_settings(
    client: FlaskClient, world: dict
) -> None:
    community = world[CLOSED]
    data = {
        "__action": "edit",
        "name": community.name,
        "description": "A club.",
        "type": "participative",
        "visibility": OPEN,
    }
    with client_login(client, world["manager"]):
        response = client.post(
            url_for("communities.settings", community_id=community.slug), data=data
        )

    assert response.status_code == 302
    assert community.visibility == OPEN
