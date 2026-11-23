# Copyright (c) 2026, Abilian SAS

"""Every POST is checked for its CSRF token, once, but on the routes that take none
(the link of an unsubscribe email)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER
from abilian.sbe.apps.notifications.tasks.social import generate_unsubscribe_token
from abilian.testing.conftest import TestConfig
from abilian.web import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


class CsrfConfig(TestConfig):
    WTF_CSRF_ENABLED = True
    # A refused request is answered, not raised in the test.
    PROPAGATE_EXCEPTIONS = False


@pytest.fixture(scope="module")
def config() -> type[TestConfig]:
    return CsrfConfig


def test_the_token_is_checked_once_for_each_request(app: Application) -> None:
    checks = [f for f in app.before_request_funcs[None] if f.__name__ == "csrf_protect"]

    assert len(checks) == 1


def test_a_post_without_its_token_is_refused_before_the_view_runs(
    community1: Community, client: FlaskClient, db: SQLAlchemy
) -> None:
    ensure_services_started(["security"])
    manager = community1.test_user
    community1.set_membership(manager, MANAGER)
    folder = community1.folder.create_subfolder("Board")
    db.session.commit()
    url = url_for(
        "documents.folder_post",
        community_id=community1.slug,
        folder_id=community1.folder.id,
    )

    with client_login(client, manager):
        response = client.post(
            url,
            data={"action": "delete", "object-selected": f"cmis:folder:{folder.id}"},
        )

    assert response.status_code == 400
    db.session.expire_all()
    assert [f.title for f in community1.folder.subfolders] == ["Board"]


def test_unsubscribing_from_the_emails_needs_no_token(
    client: FlaskClient, db: SQLAlchemy
) -> None:
    user = User(email="reader@example.com", password=uuid4().hex, can_login=True)
    db.session.add(user)
    db.session.commit()
    url = url_for(
        "notifications.unsubscribe_sbe", token=generate_unsubscribe_token(user)
    )

    response = client.post(url)

    assert response.status_code == 200
