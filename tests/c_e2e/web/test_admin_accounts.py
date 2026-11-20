# Copyright (c) 2012-2026, Abilian SAS

"""The accounts in the administration: listed by state, one account's page,
signing in as someone, and the overview that counts them."""

from __future__ import annotations

import datetime as dt
import re
from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from flask import url_for
from flask_login import current_user

from abilian.core.extensions import mail
from abilian.core.models.subjects import User
from abilian.services import security_service
from abilian.services.security import ADMIN
from tests.util import client_login

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _account(db: SQLAlchemy, last: str, **kw) -> User:
    user = User(
        first_name="Pat",
        last_name=last,
        email=f"pat.{last}@example.com".lower(),
        password=uuid4().hex,
        **kw,
    )
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture
def accounts(db: SQLAlchemy) -> dict[str, User]:
    """One account of each state, and an administrator."""
    security_service.start()
    yesterday = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(days=1)
    accounts = {
        "active": _account(db, "Active", can_login=True, last_active=yesterday),
        "invited": _account(db, "Invited", can_login=True),
        "disabled": _account(db, "Disabled", can_login=False),
        "admin": _account(db, "Admin", can_login=True, last_active=yesterday),
    }
    security_service.grant_role(accounts["admin"], ADMIN)
    db.session.commit()
    return accounts


def _page(client: FlaskClient, viewer: User, url: str) -> str:
    with client_login(client, viewer):
        response = client.get(url)
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


def _listed(html: str) -> set[str]:
    return {
        name
        for name in ("Active", "Invited", "Disabled", "Admin")
        if f"Pat {name}" in html
    }


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (None, {"Active", "Invited", "Disabled", "Admin"}),
        ("invited", {"Invited"}),
        ("disabled", {"Disabled"}),
        ("admins", {"Admin"}),
    ],
)
def test_the_accounts_are_filtered_by_state(
    state: str | None,
    expected: set[str],
    client: FlaskClient,
    admin_user: User,
    accounts: dict[str, User],
) -> None:
    html = _page(client, admin_user, url_for("admin.users", state=state, q="pat"))

    table = html.split('id="users-table"')[1]
    assert _listed(table) == expected


def test_each_state_says_how_many_accounts_it_has(
    client: FlaskClient, admin_user: User, accounts: dict[str, User]
) -> None:
    html = _page(client, admin_user, url_for("admin.users"))

    pills = html.split('class="ads-pills"')[1].split("</ul>")[0]
    # The administrator signing in counts too, among the administrators.
    assert "Never signed in (1)" in pills
    assert "Disabled (1)" in pills
    assert "Administrators (2)" in pills


def test_a_search_counts_and_keeps_what_it_found_in_each_state(
    client: FlaskClient, admin_user: User, accounts: dict[str, User]
) -> None:
    html = _page(client, admin_user, url_for("admin.users", q="dis"))

    pills = html.split('class="ads-pills"')[1].split("</ul>")[0]
    assert "All (1)" in pills
    assert "Never signed in (0)" in pills
    assert "Disabled (1)" in pills
    assert "/admin/users?state=disabled&q=dis" in pills


def test_an_accounts_page_says_where_it_is_and_when_it_came(
    client: FlaskClient, admin_user: User, accounts: dict[str, User]
) -> None:
    invited = accounts["invited"]
    html = _page(client, admin_user, url_for("admin.users_user", user_id=invited.id))

    assert "In no community." in html
    assert "Never signed in." in html
    assert url_for("admin.audit", user=invited.id) in html
    assert f'name="user" value="{invited.id}"' in html


def test_an_account_is_disabled_and_made_administrator_from_its_page(
    client: FlaskClient, admin_user: User, accounts: dict[str, User], db: SQLAlchemy
) -> None:
    """The switches post a value when on and nothing when off."""
    active = accounts["active"]
    data = {
        "first_name": "Pat",
        "last_name": "Active",
        "email": active.email,
        "roles": "admin",
        "password": "",
        "confirm_password": "",
        "__action": "edit",
    }
    with client_login(client, admin_user):
        response = client.post(
            url_for("admin.users_user", user_id=active.id), data=data
        )

    assert response.status_code == 302
    db.session.expire_all()
    assert not active.can_login
    assert ADMIN in security_service.get_roles(active, no_group_roles=True)


def test_an_administrator_gives_an_account_its_job_and_organization(
    client: FlaskClient, admin_user: User, accounts: dict[str, User], db: SQLAlchemy
) -> None:
    active = accounts["active"]
    data = {
        "first_name": "Pat",
        "last_name": "Active",
        "email": active.email,
        "can_login": "y",
        "job_title": " Librarian ",
        "organization": "x" * 201,
        "password": "",
        "confirm_password": "",
        "__action": "edit",
    }
    with client_login(client, admin_user):
        url = url_for("admin.users_user", user_id=active.id)
        too_long = client.post(url, data=data)
        saved = client.post(url, data={**data, "organization": "City Library"})

    assert too_long.status_code == 200
    assert saved.status_code == 302
    db.session.expire_all()
    assert (active.job_title, active.organization) == ("Librarian", "City Library")


def test_an_administrator_signs_in_as_someone(
    client: FlaskClient, admin_user: User, accounts: dict[str, User]
) -> None:
    active = accounts["active"]
    with client_login(client, admin_user):
        response = client.post(
            url_for("admin.impersonate_post"), data={"user": active.id}
        )
        assert response.status_code == 302
        client.get(url_for("main.home"))
        assert current_user.id == active.id


def test_a_link_does_not_sign_an_administrator_in_as_someone(
    client: FlaskClient, admin_user: User, accounts: dict[str, User]
) -> None:
    """A page or an e-mail an administrator opens could hold such a link."""
    active = accounts["active"]
    with client_login(client, admin_user):
        response = client.get(f"/admin/impersonate?email={active.email}")
        client.get(url_for("main.home"))
        assert current_user.id == admin_user.id

    assert response.status_code == 405


def test_a_refused_account_says_why_under_the_field(
    client: FlaskClient, admin_user: User, accounts: dict[str, User]
) -> None:
    active = accounts["active"]
    data = {
        "first_name": "Pat",
        "last_name": "Active",
        "email": active.email,
        "can_login": "y",
        "password": "one",
        "confirm_password": "two",
        "__action": "edit",
    }
    with client_login(client, admin_user):
        response = client.post(
            url_for("admin.users_user", user_id=active.id), data=data
        )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    field = html.split('id="password"')[1].split(">")[0]
    assert 'aria-invalid="true"' in field
    assert 'aria-describedby="password-help password-error"' in field
    assert 'id="password-error"' in html


def test_the_overview_counts_the_accounts_and_the_communities(
    client: FlaskClient,
    admin_user: User,
    accounts: dict[str, User],
    community1: Community,
) -> None:
    html = _page(client, admin_user, url_for("admin.dashboard"))

    tiles = re.findall(
        r'<span class="ads-metric">([^<]+)</span><span>([^<]+)</span>', html
    )
    figures = {label: value for value, label in tiles}
    everyone = User.query.filter(User.id != 0)
    assert figures["accounts"] == str(everyone.count())
    assert figures["communities"] == "1"
    # As the accounts' "Never signed in" counts them: not the disabled.
    never = everyone.filter(User.can_login, User.last_active.is_(None)).count()
    assert f"{never} never signed in" in html
    assert url_for("admin.users_user", user_id=accounts["active"].id) in html


def test_the_administration_shows_no_groups_vocabularies_or_tags(
    client: FlaskClient, admin_user: User, db: SQLAlchemy
) -> None:
    """People see communities, never groups; SBE uses no vocabularies and no tags."""
    html = _page(client, admin_user, url_for("admin.dashboard"))

    tabs = html.split('class="ads-tabs"')[1].split("</ul>")[0]
    assert url_for("admin.users") in tabs
    for hidden in ("admin.groups", "admin.vocabularies", "admin.tags"):
        assert url_for(hidden) not in tabs


def _act(client: FlaskClient, viewer: User, user: User, action: str):
    url = url_for("admin.users_account", user_id=user.id)
    with client_login(client, viewer):
        return client.post(url, data={"action": action})


def test_an_account_is_disabled_and_enabled_from_its_row(
    client: FlaskClient, accounts: dict[str, User], db: SQLAlchemy
) -> None:
    admin, user = accounts["admin"], accounts["active"]
    html = _page(client, admin, url_for("admin.users"))
    assert url_for("admin.users_account", user_id=user.id) in html

    assert _act(client, admin, user, "disable").status_code == 302
    db.session.refresh(user)
    assert not user.can_login

    assert _act(client, admin, user, "enable").status_code == 302
    db.session.refresh(user)
    assert user.can_login


def test_an_administrator_does_not_disable_their_own_account(
    client: FlaskClient, accounts: dict[str, User], db: SQLAlchemy
) -> None:
    admin = accounts["admin"]

    assert _act(client, admin, admin, "disable").status_code == 400
    db.session.refresh(admin)
    assert admin.can_login


def test_a_password_link_is_sent_from_an_accounts_row(
    client: FlaskClient, accounts: dict[str, User]
) -> None:
    with mail.record_messages() as outbox:
        response = _act(client, accounts["admin"], accounts["invited"], "send-link")

    assert response.status_code == 302
    assert [m.recipients for m in outbox] == [[accounts["invited"].email]]


def test_only_an_administrator_acts_on_an_account(
    client: FlaskClient, accounts: dict[str, User], db: SQLAlchemy
) -> None:
    user = accounts["active"]

    response = _act(client, accounts["invited"], user, "disable")

    assert response.status_code == 403
    db.session.refresh(user)
    assert user.can_login
