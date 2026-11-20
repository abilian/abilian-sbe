# Copyright (c) 2012-2026, Abilian SAS

"""Inviting people: from a dialog on every page of the community; what will happen to
each address, said as they are typed; typed addresses are invited at once, with one
role for all and a word to go with the invitation, an account made for each that has
none, unnamed until its person arrives; a spreadsheet's list is checked on a page
first. Each one added is told by e-mail, and whoever never signed in gets the link to
choose a password."""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import smtplib
from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import sqlalchemy as sa

from abilian.core.extensions import mail
from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.sbe.apps.communities.views import wizard
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


def test_typed_addresses_are_invited_at_once_with_their_role(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    """No page for the names of the accounts to make: their people give them."""
    data = {
        "wizard-emails": "account@example.com new@x.org",
        "role": "manager",
        "note": "Welcome to the board.",
    }
    with client_login(client, people["manager"]), mail.record_messages() as outbox:
        response = client.post(
            url_for("communities.wizard_check_data", community_id=community1.slug),
            data=data,
        )

    assert response.status_code == 302
    new = User.query.filter(User.email == "new@x.org").one()
    assert (new.first_name, new.last_name, new.name) == (None, None, "new")
    assert community1.get_role(new) == MANAGER
    assert community1.get_role(people["account"]) == MANAGER
    assert sorted(message.recipients[0] for message in outbox) == [
        "account@example.com",
        "new@x.org",
    ]
    assert all("Welcome to the board." in message.body for message in outbox)


def test_each_one_added_is_told_with_the_word_that_came_with_it(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    accounts = _existing("invited@example.com", "account@example.com")

    _status, outbox = _saving(
        client, people["manager"], community1, accounts, note="See you Monday."
    )

    told = {message.recipients[0]: message for message in outbox}
    assert set(told) == {account["email"] for account in accounts}
    for message in told.values():
        assert community1.name in message.subject
        assert people["manager"].name in message.subject
        assert "See you Monday." in message.body
    # Whoever never signed in chooses a password; the others find the community.
    any_token = uuid4().hex
    choose = url_for("login.reset_password", token=any_token).removesuffix(any_token)
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


def _existing(*emails: str, role: str = "member") -> list[dict[str, str]]:
    """Accounts there are, as the second page's script sends them."""
    return [{"email": email, "status": "existing", "role": role} for email in emails]


def _saving(
    client: FlaskClient,
    manager: User,
    community: Community,
    entries: list[dict[str, str]],
    **data,
) -> tuple[int, list]:
    with client_login(client, manager), mail.record_messages() as outbox:
        response = client.post(
            url_for("communities.wizard_saving", community_id=community.slug),
            data={"wizard-emails": json.dumps(entries), **data},
        )
    return response.status_code, outbox


def test_an_address_is_the_same_whatever_its_case(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    data = {
        "wizard-emails": "ACCOUNT@example.com new@x.org New@X.org",
        "role": "member",
    }
    with client_login(client, people["manager"]):
        response = client.post(
            url_for("communities.wizard_check_data", community_id=community1.slug),
            data=data,
        )

    # The account is found, not made again; the new address makes one account.
    assert response.status_code == 302
    assert community1.get_role(people["account"]) == MEMBER
    made = User.query.filter(sa.func.lower(User.email) == "new@x.org").all()
    assert len(made) == 1


def test_a_role_one_is_not_invited_with_is_refused(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    status, outbox = _saving(
        client,
        people["manager"],
        community1,
        _existing("account@example.com", role="Manager"),
    )

    assert status == 400
    assert outbox == []
    assert community1.get_role(people["account"]) is None


def test_a_spreadsheets_role_is_read_whatever_its_case(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    csv = io.BytesIO(b"carla@x.org;Carla;Csv;Manager\nCARLA@x.org;C;C;member\n")

    html = _post(
        client,
        people["manager"],
        "communities.wizard_check_data",
        community1,
        csv_file=(csv, "people.csv"),
    )

    value = re.search(r'name="wizard-emails" value="([^"]*)"', html)
    assert value
    accounts = json.loads(unescape(value.group(1)))
    assert [(a["email"], a["role"]) for a in accounts] == [("carla@x.org", "manager")]


def test_all_are_added_before_anyone_is_told_and_the_untold_are_named(
    client: FlaskClient,
    community1: Community,
    people: dict[str, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_the_first(user, community, inviter, note) -> None:
        if user.email == "invited@example.com":
            raise smtplib.SMTPRecipientsRefused({user.email: (550, b"no")})

    monkeypatch.setattr(wizard, "send_invitation", refuse_the_first)
    accounts = _existing("invited@example.com", "account@example.com")

    with client_login(client, people["manager"]):
        client.post(
            url_for("communities.wizard_saving", community_id=community1.slug),
            data={"wizard-emails": json.dumps(accounts)},
        )
        html = unescape(
            client.get(
                url_for("communities.members", community_id=community1.slug)
            ).get_data(as_text=True)
        )

    assert community1.get_role(people["invited"]) == MEMBER
    assert community1.get_role(people["account"]) == MEMBER
    assert "not told by e-mail, which could not be sent: invited@example.com" in html


def test_a_spreadsheets_new_accounts_are_checked_then_made_with_its_names(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    csv = io.BytesIO(b"dora@x.org;Dora;Csv;member\n")

    html = _post(
        client,
        people["manager"],
        "communities.wizard_check_data",
        community1,
        csv_file=(csv, "people.csv"),
    )

    assert "Dora Csv" in html
    value = re.search(r'name="wizard-emails" value="([^"]*)"', html)
    assert value
    status, _outbox = _saving(
        client, people["manager"], community1, json.loads(unescape(value.group(1)))
    )
    assert status == 302
    dora = User.query.filter(User.email == "dora@x.org").one()
    assert (dora.first_name, dora.last_name) == ("Dora", "Csv")
    # The header's button leads to the first page here: there is no dialog.
    assert 'data-modal-open="#modal-invite"' not in html


def test_the_invitation_speaks_the_language_of_whoever_is_invited(
    client: FlaskClient,
    community1: Community,
    people: dict[str, User],
    db: SQLAlchemy,
) -> None:
    people["account"].locale = "fr"
    db.session.commit()

    _status, outbox = _saving(
        client, people["manager"], community1, _existing("account@example.com")
    )

    (message,) = outbox
    assert " vous invite dans " in message.subject
    assert "vous a ajouté à la communauté" in message.body


def test_the_steps_say_which_is_current_and_each_row_whose_it_is(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    html = _post(
        client,
        people["manager"],
        "communities.wizard_check_data",
        community1,
        csv_file=(io.BytesIO(b"new@x.org;;;member\n"), "people.csv"),
    )

    assert html.count('aria-current="step"') == 1
    assert html.count('class="ads-step sbe-step--done"') == 1
    assert 'aria-label="Role of new@x.org"' in html
    assert 'aria-label="Remove new@x.org"' in html


def test_typing_addresses_tells_a_screen_reader_the_count_only(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    with client_login(client, people["manager"]):
        page = client.get(
            url_for("communities.wizard_data_insertion", community_id=community1.slug)
        ).get_data(as_text=True)

    assert 'role="status" data-preview-status="wizard-emails"' in page
    assert "aria-live" not in page.split("data-preview=")[1].split(">")[0]
