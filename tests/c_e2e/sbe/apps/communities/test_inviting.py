# Copyright (c) 2012-2026, Abilian SAS

"""Inviting people: from a dialog on every page of the community; what will happen to
each address, said as they are typed; typed addresses go on to the accounts to make,
with one role for all and a word to go with the invitation; each one added is told by
e-mail, and whoever never signed in gets the link to choose a password."""

from __future__ import annotations

import datetime as dt
import json
import re
from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from abilian.core.extensions import mail
from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _account(db: SQLAlchemy, email: str, *, signed_in: bool) -> User:
    last_active = dt.datetime(2026, 1, 5) if signed_in else None
    user = User(
        email=email,
        password=uuid4().hex,
        can_login=True,
        last_active=last_active,
    )
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture
def people(community1: Community, db: SQLAlchemy) -> dict[str, User]:
    ensure_services_started(["security"])
    people = {
        "manager": _account(db, "manager@example.com", signed_in=True),
        "member": _account(db, "member@example.com", signed_in=True),
        "account": _account(db, "account@example.com", signed_in=True),
        "invited": _account(db, "invited@example.com", signed_in=False),
    }
    community1.set_membership(people["manager"], MANAGER)
    community1.set_membership(people["member"], MEMBER)
    db.session.commit()
    return people


def _post(
    client: FlaskClient, user: User, endpoint: str, community: Community, **data
) -> str:
    with client_login(client, user):
        response = client.post(
            url_for(endpoint, community_id=community.slug), data=data
        )
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_each_address_says_what_inviting_does_to_it(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    typed = (
        "member@example.com, Account@example.com\ninvited@example.com new@x.org nope"
    )

    html = _post(
        client,
        people["manager"],
        "communities.wizard_preview",
        community1,
        **{"wizard-emails": typed},
    )

    html = unescape(html)
    assert "Already a member: nothing to do" in html
    assert "Has an account: will be added, and told by email" in html
    assert "Invited already, never signed in" in html
    assert "No account: one will be made" in html
    assert "Not an address: it will be left out" in html
    assert "3 people will get an email." in html


def test_typed_addresses_go_on_to_the_accounts_to_make_with_their_role(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    html = _post(
        client,
        people["manager"],
        "communities.wizard_check_data",
        community1,
        **{
            "wizard-emails": "account@example.com new@x.org",
            "role": "manager",
            "note": "Welcome to the board.",
        },
    )

    assert '<input type="hidden" name="account" value="new@x.org">' in html
    value = re.search(r'name="existing_account" value="([^"]*)"', html)
    assert value
    carried = json.loads(unescape(value.group(1)))
    assert carried == {"account@example.com": "manager"}
    assert '<input type="hidden" name="note" value="Welcome to the board.">' in html


def test_each_one_added_is_told_with_the_word_that_came_with_it(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    accounts = {"invited@example.com": "member", "account@example.com": "member"}

    with client_login(client, people["manager"]), mail.record_messages() as outbox:
        client.post(
            url_for("communities.wizard_saving", community_id=community1.slug),
            data={"existing_account": json.dumps(accounts), "note": "See you Monday."},
        )

    told = {message.recipients[0]: message for message in outbox}
    assert set(told) == set(accounts)
    for message in told.values():
        assert community1.name in message.subject
        assert people["manager"].name in message.subject
        assert "See you Monday." in message.body
    # Whoever never signed in chooses a password; the others find the community.
    choose = url_for("login.reset_password", token="TOKEN").removesuffix("TOKEN")
    assert choose in told["invited@example.com"].body
    community_url = url_for(community1, _external=True)
    assert community_url in told["account@example.com"].body
    assert community1.get_role(people["invited"]) == MEMBER
    assert community1.get_role(people["account"]) == MEMBER


def test_a_managers_pages_invite_from_a_dialog(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    home = url_for("wall.index", community_id=community1.slug)
    first_page = url_for(
        "communities.wizard_data_insertion", community_id=community1.slug
    )

    with client_login(client, people["manager"]):
        managed = client.get(home).get_data(as_text=True)
        page = client.get(first_page).get_data(as_text=True)
    with client_login(client, people["member"]):
        seen = client.get(home).get_data(as_text=True)

    assert 'id="modal-invite"' in managed
    assert 'data-modal-open="#modal-invite"' in managed
    # The first page has the same fields: not twice.
    assert 'id="modal-invite"' not in page
    assert page.count('id="wizard-emails"') == 1
    assert 'id="modal-invite"' not in seen


def test_a_member_sees_no_preview(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    with client_login(client, people["member"]):
        response = client.post(
            url_for("communities.wizard_preview", community_id=community1.slug),
            data={"wizard-emails": "account@example.com"},
        )

    assert response.status_code == 403
