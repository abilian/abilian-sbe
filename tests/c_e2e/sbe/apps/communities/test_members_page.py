# Copyright (c) 2012-2026, Abilian SAS

"""A community's members on the Abilian Design System: its managers filtered out,
and what is offered to whom.

The table's columns are in `test_members_table.py`, its filter and sort in
`test_listings.py`.
"""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from flask import url_for

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from werkzeug.test import TestResponse

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _person(db: SQLAlchemy, community: Community, last: str, role) -> User:
    user = User(
        first_name="Ann",
        last_name=last,
        email=f"{uuid4().hex}@example.com",
        password=uuid4().hex,
        can_login=True,
    )
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    return user


@pytest.fixture
def people(community1: Community, db: SQLAlchemy) -> dict[str, User]:
    ensure_services_started(["security"])
    people = {
        "manager": _person(db, community1, "Manager", MANAGER),
        "member": _person(db, community1, "Member", MEMBER),
    }
    db.session.commit()
    return people


def _page(client: FlaskClient, user: User, community: Community, **args) -> str:
    with client_login(client, user):
        response = client.get(
            url_for("communities.members", community_id=community.slug, **args)
        )
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


def test_the_managers_are_one_pill_away(
    people: dict[str, User], community1: Community, client: FlaskClient
) -> None:
    html = _page(client, people["member"], community1, role="manager")

    rows = html.split("<tbody>")[1]
    assert "Ann Manager" in rows
    assert "Ann Member" not in rows
    assert 'aria-current="page">Managers (1)' in html


def test_a_member_reads_the_list_and_changes_nothing(
    people: dict[str, User], community1: Community, client: FlaskClient
) -> None:
    html = _page(client, people["member"], community1)

    assert 'id="add-user-role"' not in html
    assert 'name="role" data-autosubmit' not in html
    assert "modal-remove-" not in html


def test_a_manager_is_asked_before_removing_someone(
    people: dict[str, User], community1: Community, client: FlaskClient
) -> None:
    html = _page(client, people["manager"], community1)

    assert 'id="add-user-role"' in html
    dialog = html.split('aria-labelledby="modal-remove-')[2]
    assert "from the community?" in dialog
    assert 'name="action" value="delete"' in dialog


def _act_on(
    client: FlaskClient, manager: User, community: Community, action: str, *users: User
) -> TestResponse:
    url = url_for("communities.members_post", community_id=community.slug)
    data = {"action": action, "selected": [str(u.id) for u in users]}
    with client_login(client, manager):
        return client.post(url, data=data)


def test_a_manager_selects_members_to_make_them_managers(
    client: FlaskClient, community1: Community, people: dict[str, User], db: SQLAlchemy
) -> None:
    html = _page(client, people["manager"], community1)
    assert 'form="members-selection"' in html

    response = _act_on(
        client, people["manager"], community1, "selection-managers", people["member"]
    )

    assert response.status_code == 302
    assert community1.get_role(people["member"]) == MANAGER


def test_a_manager_removes_the_selected_members_and_no_one_else(
    client: FlaskClient,
    community1: Community,
    community2: Community,
    people: dict[str, User],
    db: SQLAlchemy,
) -> None:
    outsider = _person(db, community2, "Outsider", MEMBER)
    db.session.commit()

    _act_on(
        client,
        people["manager"],
        community1,
        "selection-remove",
        people["member"],
        outsider,
    )

    assert community1.get_role(people["member"]) is None
    assert community2.get_role(outsider) == MEMBER


def test_a_member_does_not_act_on_a_selection(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    html = _page(client, people["member"], community1)
    assert 'form="members-selection"' not in html

    response = _act_on(
        client, people["member"], community1, "selection-remove", people["manager"]
    )

    assert response.status_code == 403
    assert community1.get_role(people["manager"]) == MANAGER


def test_a_community_keeps_at_least_one_manager(
    client: FlaskClient, community1: Community, people: dict[str, User]
) -> None:
    manager = people["manager"]
    everyone = (manager, people["member"])

    removed = _act_on(client, manager, community1, "selection-remove", *everyone)
    demoted = _act_on(client, manager, community1, "selection-members", manager)
    url = url_for("communities.members_post", community_id=community1.slug)
    with client_login(client, manager):
        alone = client.post(
            url, data={"action": "set-user-role", "user": manager.id, "role": "member"}
        )
        garbled = client.post(url, data={"action": "selection-remove", "selected": "x"})

    assert {removed.status_code, demoted.status_code, alone.status_code} == {302}
    assert community1.get_role(manager) == MANAGER
    assert community1.get_role(people["member"]) == MEMBER
    assert garbled.status_code == 302
