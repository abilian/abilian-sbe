# Copyright (c) 2012-2024, Abilian SAS

"""The members' tables render as many cells as they have columns.

The members table and the invitation's table once came from macros that each
asked whether the viewer manages the community, and did not ask the same way: the
header dropped a column while the rows kept its cells. `can_manage_community` is
defined for every community template, and each page now draws its own table.
"""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

import pytest
from flask import render_template_string, url_for

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities import security as community_security
from abilian.sbe.apps.communities.models import MANAGER, READER
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


def _member(db: SQLAlchemy, community: Community, email: str, role) -> User:
    user = User(email=email, password="test", can_login=True)  # noqa: S106
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    db.session.flush()
    return user


def _columns_and_cells(html: str) -> tuple[int, list[int]]:
    """(number of <th>, cells in each <tbody> row)."""
    thead = re.search(r"<thead.*?</thead>", html, re.DOTALL)
    tbody = re.search(r"<tbody.*?</tbody>", html, re.DOTALL)
    assert thead, "no <thead> in the page"
    assert tbody, "no <tbody> in the page"

    columns = len(re.findall(r"<th\b", thead.group(0)))
    rows = re.findall(r"<tr\b.*?</tr>", tbody.group(0), re.DOTALL)
    return columns, [len(re.findall(r"<td\b", row)) for row in rows]


@pytest.mark.parametrize("role", [MANAGER, READER])
def test_every_row_has_one_cell_per_column(
    role, community1: Community, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    ensure_services_started(["security"])
    viewer = _member(db, community1, "viewer@example.com", role)

    with client_login(client, viewer):
        response = client.get(
            url_for("communities.members", community_id=community1.slug)
        )
    assert response.status_code == 200

    columns, rows = _columns_and_cells(response.get_data(as_text=True))
    assert rows, "no member rows rendered"
    for cells in rows:
        assert cells == columns, (
            f"{cells} cells against {columns} columns as {role}: the header and "
            "the row disagree about whether the manager column is there"
        )


def test_can_manage_community_is_defined_for_every_community_template(
    community1: Community, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    """Supplied by the context processor, not by each view.

    Undefined is the state the two branches disagreed about, so the fix is that
    it never is.
    """
    ensure_services_started(["security"])
    manager = _member(db, community1, "manager@example.com", MANAGER)

    with client_login(client, manager):
        # any request inside the community puts g.community in place
        client.get(url_for("communities.members", community_id=community1.slug))
        with client.application.test_request_context(
            f"/communities/{community1.slug}/members"
        ):
            from flask import g

            g.community = community1
            rendered = render_template_string("{{ can_manage_community is defined }}")

    assert rendered == "True"


def test_a_template_that_does_not_ask_never_reaches_the_community(
    community1: Community, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    """Error pages render after the session holding `g.community` is gone.

    `_remove_session_save_objects` keeps the models on `g`, but `g.community` is
    a presenter, so it stays detached. Reading it there replaced the error page
    with a raw 500. That method does nothing under `testing`, so this detaches
    the community by hand.
    """
    db.session.commit()
    db.session.expunge(community1)

    with client.application.test_request_context("/"):
        from flask import g

        g.community = community1
        assert render_template_string("fine") == "fine"


def test_the_manager_check_does_not_run_once_per_row(
    community1: Community,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each row's macro reads `can_manage_community`, and each check costs queries."""
    ensure_services_started(["security"])
    manager = _member(db, community1, "manager@example.com", MANAGER)
    checks = []
    can_manage = community_security.can_manage

    def counting_can_manage(*args, **kwargs) -> bool:
        checks.append(args)
        return can_manage(*args, **kwargs)

    monkeypatch.setattr(community_security, "can_manage", counting_can_manage)
    url = url_for("communities.members", community_id=community1.slug)

    with client_login(client, manager):
        assert client.get(url).status_code == 200
        checks_for_one_member = len(checks)

        for i in range(5):
            _member(db, community1, f"member{i}@example.com", READER)
        db.session.commit()
        checks.clear()

        assert client.get(url).status_code == 200

    assert len(checks) == checks_for_one_member


def test_inviting_lists_the_new_accounts_one_cell_per_column(
    community1: Community, db: SQLAlchemy, client: FlaskClient, app: Application
) -> None:
    """A spreadsheet's addresses go on to a page that checks them, whose header and
    rows once came from macros that disagreed about the manager column; only
    managers reach it."""
    ensure_services_started(["security"])
    manager = _member(db, community1, "wizard-manager@example.com", MANAGER)
    db.session.flush()

    with client_login(client, manager):
        response = client.post(
            url_for("communities.wizard_check_data", community_id=community1.slug),
            data={
                "csv_file": (io.BytesIO(b"no.account@example.com;;;member\n"), "a.csv")
            },
        )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    columns, _cells = _columns_and_cells(html)
    rows = re.findall(r"<tr data-wizard-row>.*?</tr>", html, re.DOTALL)
    assert len(rows) == 1
    assert len(re.findall(r"<td\b", rows[0])) == columns
