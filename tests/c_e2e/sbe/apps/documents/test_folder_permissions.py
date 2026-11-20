# Copyright (c) 2026, Abilian SAS

"""A folder's permissions say who has access in people's words: the community's
members, as on the folder above, or only the people given a role here. No group."""

from __future__ import annotations

from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from flask_login import login_user

from abilian.core.models.subjects import Group, User
from abilian.sbe.apps.communities.models import MANAGER
from abilian.services import security_service
from abilian.services.security import READER
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community
    from abilian.sbe.apps.documents.models import Folder


@pytest.fixture
def manager(community1: Community, db: SQLAlchemy) -> User:
    ensure_services_started(["security"])
    community1.set_membership(community1.test_user, MANAGER)
    db.session.commit()
    return community1.test_user


@pytest.fixture
def folder(community1: Community, manager: User, db: SQLAlchemy) -> Folder:
    folder = community1.folder.create_subfolder("Board")
    db.session.commit()
    return folder


def _url(folder: Folder, endpoint: str = "documents.permissions") -> str:
    return url_for(endpoint, community_id=folder.community.slug, folder_id=folder.id)


def _page(client: FlaskClient, user: User, folder: Folder) -> str:
    with client_login(client, user):
        response = client.get(_url(folder))
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


def test_an_inheriting_folder_is_open_to_the_communitys_members(
    client: FlaskClient, manager: User, folder: Folder
) -> None:
    html = _page(client, manager, folder)

    assert "The community's members, as on the folder above" in html
    assert 'id="deactivate_inheritance"' in html
    assert "Through the folder above" in html
    assert "group" not in html.lower().replace("ads-btn-group", "")


def test_a_folder_kept_to_its_people_says_so(
    client: FlaskClient, manager: User, folder: Folder, db: SQLAlchemy
) -> None:
    with client_login(client, manager):
        client.post(
            _url(folder, "documents.permissions_update"),
            data={"action": "add-user-role", "user": manager.id, "role": "manager"},
        )
        client.post(
            _url(folder, "documents.permissions_update"),
            data={"action": "deactivate_inheritance"},
        )

    html = _page(client, manager, folder)

    assert "Only the people given a role here" in html
    assert 'id="activate_inheritance"' in html
    assert "Through the folder above" not in html
    assert f'value="manager:{manager.id}"' in html


def test_a_role_given_here_can_be_taken_back(
    client: FlaskClient, manager: User, folder: Folder, db: SQLAlchemy
) -> None:
    other = User(
        first_name="Pat",
        last_name="Other",
        email="pat.other@example.com",
        password=uuid4().hex,
        can_login=True,
    )
    db.session.add(other)
    db.session.commit()
    with client_login(client, manager):
        client.post(
            _url(folder, "documents.permissions_update"),
            data={"action": "add-user-role", "user": other.id, "role": READER.name},
        )

    html = _page(client, manager, folder)

    assert f'name="delete-user-role" value="reader:{other.id}"' in html


def test_a_groups_name_is_shown_as_text_in_the_history(
    app: Flask, client: FlaskClient, manager: User, folder: Folder, db: SQLAlchemy
) -> None:
    group = Group(name="<img src=x onerror=alert(1)>")
    db.session.add(group)
    db.session.flush()
    with app.test_request_context():
        login_user(manager)
        security_service.grant_role(group, READER, folder)
        db.session.commit()

    with client_login(client, manager):
        html = client.get(_url(folder)).get_data(as_text=True)

    assert "<img src=x onerror" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_the_permissions_lead_back_to_their_folder(
    client: FlaskClient, manager: User, folder: Folder
) -> None:
    html = _page(client, manager, folder)

    crumbs = html.split('<ol class="ads-breadcrumb">')[1].split("</ol>")[0]
    assert f'<a href="{url_for(folder)}">{folder.title}</a>' in crumbs
