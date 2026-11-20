# Copyright (c) 2012-2024, Abilian SAS

"""The template gate that step 2 rewrote, seen from both sides.

`document.html` shows who has read a document, gated on `can_manage(g.community)`
where it used to read `g.is_manager`. The browser suite logs in as a site admin,
for whom every one of these gates is open, so it cannot tell the rewritten
condition from one that is simply always true. These are the negative cases.

Rendering it at all is worth an assertion of its own: the gate calls a Jinja
global, and Jinja raises on calling an undefined -- so a missing registration is
a 500 on this page and nothing else would notice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import url_for
from pytest import fixture

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, READER
from abilian.services import security_service
from abilian.services.security import ADMIN
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community

#: The panel `can_manage(g.community)` gates.
READERS_PANEL = 'id="readers"'


@fixture
def document(community1: Community, db: SQLAlchemy):
    doc = community1.folder.create_document(title="Gated.txt")
    doc.set_content(b"content", "text/plain")
    doc.owner = doc.creator = community1.test_user
    db.session.flush()
    return doc


def _member(db: SQLAlchemy, community: Community, email: str, role) -> User:
    user = User(email=email, password="test", can_login=True)  # noqa: S106
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    db.session.flush()
    return user


def _get(client: FlaskClient, community: Community, doc) -> str:
    response = client.get(
        url_for("documents.document_view", community_id=community.slug, doc_id=doc.id)
    )
    assert response.status_code == 200, f"document page returned {response.status_code}"
    return response.get_data(as_text=True)


def test_a_community_manager_sees_who_has_read_it(
    community1: Community,
    document,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    ensure_services_started(["security"])
    manager = _member(db, community1, "manager@example.com", MANAGER)

    with client_login(client, manager):
        assert READERS_PANEL in _get(client, community1, document)


def test_a_plain_member_does_not(
    community1: Community,
    document,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    """The assertion the browser suite cannot make: it is always an admin."""
    ensure_services_started(["security"])
    reader = _member(db, community1, "reader@example.com", READER)

    with client_login(client, reader):
        assert READERS_PANEL not in _get(client, community1, document)


def test_a_site_admin_sees_it_in_a_community_they_do_not_manage(
    community1: Community,
    document,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    ensure_services_started(["security"])
    admin = _member(db, community1, "admin@example.com", READER)
    security_service.grant_role(admin, ADMIN)
    db.session.flush()

    with client_login(client, admin):
        assert READERS_PANEL in _get(client, community1, document)


def _post_lock(client: FlaskClient, community: Community, doc, action: str) -> int:
    return client.post(
        url_for(
            "documents.checkin_checkout", community_id=community.slug, doc_id=doc.id
        ),
        data={"action": action},
    ).status_code


def test_a_reader_can_download_a_selection_from_a_folder(
    community1: Community,
    document,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    """Downloading needs nothing but seeing the folder; moving and deleting need
    the right to write in it."""
    ensure_services_started(["security"])
    reader = _member(db, community1, "reader@example.com", READER)

    with client_login(client, reader):
        response = client.get(
            url_for(
                "documents.folder_view",
                community_id=community1.slug,
                folder_id=community1.folder.id,
            )
        )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    bar = html.split('class="ads-bulkbar"')[1].split("</div>")[0]
    assert 'value="download"' in bar
    assert 'value="delete"' not in bar
    assert "#modal-move-files" not in bar


def test_a_manager_can_check_out(
    community1: Community,
    document,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    ensure_services_started(["security"])
    manager = _member(db, community1, "manager@example.com", MANAGER)

    with client_login(client, manager):
        assert _post_lock(client, community1, document, "checkout") == 200
        db.session.expire(document)
        assert document.lock is not None


def test_a_reader_cannot_lock_or_unlock(
    community1: Community,
    document,
    db: SQLAlchemy,
    client: FlaskClient,
    app: Application,
) -> None:
    """A lock stops others uploading, so it takes write access to change one."""
    ensure_services_started(["security"])
    reader = _member(db, community1, "reader@example.com", READER)
    manager = _member(db, community1, "manager@example.com", MANAGER)
    with client_login(client, manager):
        assert _post_lock(client, community1, document, "checkout") == 200

    with client_login(client, reader):
        assert _post_lock(client, community1, document, "unlock") == 403
        assert _post_lock(client, community1, document, "checkout") == 403

    db.session.expire(document)
    assert document.lock.user_id == manager.id
