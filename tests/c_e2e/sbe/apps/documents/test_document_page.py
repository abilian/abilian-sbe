# Copyright (c) 2012-2026, Abilian SAS

"""A document's page on the Abilian Design System: its history, and what is offered
to whom.

Who sees its readers is in `test_document_gating.py`.
"""

from __future__ import annotations

from html import unescape
from io import BytesIO
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.sbe.apps.documents.views.documents import document_history
from abilian.services import audit_service
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community
    from abilian.sbe.apps.documents.models import Document

NEW_VERSION = 'data-modal-open="#modal-upload-new-version"'
LOCK = 'name="action" value="lock"'


@pytest.fixture
def audited(manager: User) -> None:
    """The audit trail, which a document's history is read from.

    Started once the community and its manager are there: the fixtures make them
    with no one logged in, which the audit would record as the system user, whom
    the test database does not hold.
    """
    ensure_services_started(["audit"])


@pytest.fixture
def manager(community1: Community, db: SQLAlchemy) -> User:
    ensure_services_started(["security"])
    community1.set_membership(community1.test_user, MANAGER)
    db.session.commit()
    return community1.test_user


@pytest.fixture
def document(community1: Community, manager: User, client: FlaskClient) -> Document:
    """A document uploaded by the manager, as the page's form does it."""
    folder = community1.folder
    with client_login(client, manager):
        response = client.post(
            url_for(
                "documents.folder_post",
                community_id=community1.slug,
                folder_id=folder.id,
            ),
            data={
                "file": (BytesIO(b"one"), "minutes.txt", "text/plain"),
                "action": "upload",
            },
        )
    assert response.status_code == 302
    (doc,) = folder.children
    return doc


def _member(db: SQLAlchemy, community: Community, role) -> User:
    user = User(
        email=f"{uuid4().hex}@example.com", password=uuid4().hex, can_login=True
    )
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    db.session.commit()
    return user


def _post(client: FlaskClient, endpoint: str, doc: Document, **data) -> int:
    url = url_for(endpoint, community_id=doc.community.slug, doc_id=doc.id)
    return client.post(url, data=data).status_code


def _page(client: FlaskClient, user: User, doc: Document) -> str:
    with client_login(client, user):
        response = client.get(url_for(doc))
    assert response.status_code == 200
    return unescape(response.get_data(as_text=True))


@pytest.mark.usefixtures("audited")
def test_the_history_tells_uploads_versions_and_edits_newest_first(
    document: Document, manager: User, client: FlaskClient
) -> None:
    with client_login(client, manager):
        new = {"file": (BytesIO(b"two two"), "minutes.txt", "text/plain")}
        assert _post(client, "documents.document_upload", document, **new) == 302
        renamed = {"title": "minutes-2026.txt", "description": "Approved"}
        assert _post(client, "documents.document_edit", document, **renamed) == 302
        # A lock is no step of the history.
        assert _post(client, "documents.checkin_checkout", document, action="lock")

    history = document_history(audit_service.entries_for(document))

    assert [change.kind for change in history] == ["edited", "new-version", "created"]


def test_a_reader_may_download_and_nothing_else(
    community1: Community, document: Document, client: FlaskClient, db: SQLAlchemy
) -> None:
    # The members of a community that is not participative read its documents.
    reader = _member(db, community1, MEMBER)

    html = _page(client, reader, document)

    assert "Download" in html
    assert NEW_VERSION not in html
    assert LOCK not in html
    assert 'id="modal-delete"' not in html
    assert "More actions on the document" not in html
