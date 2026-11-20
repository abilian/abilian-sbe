# Copyright (c) 2012-2026, Abilian SAS

"""A document's page on the Abilian Design System: its history and comments, what is
offered to whom, and the lock, which keeps the others from uploading a version.

Who sees its readers is in `test_document_gating.py`.
"""

from __future__ import annotations

from html import unescape
from io import BytesIO
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from abilian.core.extensions import mail
from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.sbe.apps.documents.views.documents import document_history
from abilian.services import audit_service, security_service
from abilian.services.security import WRITER
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community
    from abilian.sbe.apps.documents.models import Document

NEW_VERSION = 'data-modal-open="#modal-upload-new-version"'
LOCK = 'name="action" value="lock"'
UNLOCK = 'name="action" value="unlock"'


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


def test_a_document_locked_by_someone_else_takes_no_version_from_another(
    community1: Community,
    document: Document,
    manager: User,
    client: FlaskClient,
    db: SQLAlchemy,
) -> None:
    other = _member(db, community1, MANAGER)
    with client_login(client, manager):
        assert _post(client, "documents.checkin_checkout", document, action="lock")

    html = _page(client, other, document)
    with client_login(client, other):
        new = {"file": (BytesIO(b"theirs"), "minutes.txt", "text/plain")}
        status = _post(client, "documents.document_upload", document, **new)

    assert NEW_VERSION not in html
    assert UNLOCK in html
    assert status == 403
    db.session.expire(document)
    assert document.content == b"one"


def test_a_writer_neither_lifts_nor_takes_over_someone_elses_lock(
    community1: Community,
    document: Document,
    manager: User,
    client: FlaskClient,
    db: SQLAlchemy,
) -> None:
    community1.type = "participative"
    db.session.commit()
    writer = _member(db, community1, MEMBER)
    with client_login(client, manager):
        assert _post(client, "documents.checkin_checkout", document, action="lock")

    html = _page(client, writer, document)
    with client_login(client, writer):
        unlock = _post(client, "documents.checkin_checkout", document, action="unlock")
        take = _post(client, "documents.checkin_checkout", document, action="lock")

    assert UNLOCK not in html
    assert (unlock, take) == (403, 403)
    db.session.expire(document)
    assert document.lock.is_owner(manager)


def test_whoever_locked_it_uploads_the_next_version_which_unlocks_it(
    document: Document, manager: User, client: FlaskClient, db: SQLAlchemy
) -> None:
    with client_login(client, manager):
        assert _post(client, "documents.checkin_checkout", document, action="lock")
    html = _page(client, manager, document)
    with client_login(client, manager):
        new = {"file": (BytesIO(b"mine"), "minutes.txt", "text/plain")}
        status = _post(client, "documents.document_upload", document, **new)

    assert NEW_VERSION in html
    assert status == 302
    db.session.expire(document)
    assert document.content == b"mine"
    assert document.lock is None


def test_refreshing_the_preview_comes_back_to_the_document(
    document: Document, manager: User, client: FlaskClient
) -> None:
    """The conversion closes the request's session, which detached the document
    before the redirect to it was built.

    The test shares that session, so the user is detached too, and logging out
    would fail: the test does not log out.
    """
    url = url_for(document)
    refresh = url_for(
        "documents.refresh_preview",
        community_id=document.community.slug,
        doc_id=document.id,
    )
    client_login(client, manager)

    response = client.get(refresh)

    assert response.status_code == 302
    assert response.location.endswith(url)


COMMENT_FORM = 'name="body"'
COMMENT_ACTIONS = 'aria-label="Actions on the comment"'


def _comment(client: FlaskClient, doc: Document, body: str):
    url = url_for("comments.create", entity_id=doc.id)
    return client.post(url, data={"body": body, "__action": "edit"})


def test_a_writer_comments_on_the_document(
    document: Document, manager: User, client: FlaskClient
) -> None:
    with client_login(client, manager):
        response = _comment(client, document, "Approved.\nSee page 2.")
    html = _page(client, manager, document)

    assert response.status_code == 302
    (comment,) = document.__comments__
    assert response.location.endswith(f"{url_for(document)}#comment-{comment.id}")
    assert "1 comment" in html
    assert "Approved.\nSee page 2." in html
    assert COMMENT_ACTIONS in html


def test_a_reader_reads_the_comments_and_does_not_comment(
    community1: Community,
    document: Document,
    manager: User,
    client: FlaskClient,
    db: SQLAlchemy,
) -> None:
    reader = _member(db, community1, MEMBER)
    with client_login(client, manager):
        _comment(client, document, "Approved.")

    html = _page(client, reader, document)
    with client_login(client, reader):
        response = _comment(client, document, "Me too.")

    assert "Approved." in html
    assert COMMENT_FORM not in html
    assert COMMENT_ACTIONS not in html
    assert response.status_code == 403
    assert [c.body for c in document.__comments__] == ["Approved."]


def test_one_who_may_not_open_the_document_does_not_comment_on_it(
    document: Document, client: FlaskClient, db: SQLAlchemy
) -> None:
    """A role on its folder is not enough: one must be in its community."""
    outsider = User(
        email=f"{uuid4().hex}@example.com", password=uuid4().hex, can_login=True
    )
    db.session.add(outsider)
    db.session.flush()
    security_service.grant_role(outsider, WRITER, document.parent)
    db.session.commit()

    with client_login(client, outsider):
        response = _comment(client, document, "Let me in.")

    assert response.status_code == 403
    assert document.__comments__ == []


def test_the_author_edits_then_deletes_their_comment(
    document: Document, manager: User, client: FlaskClient, db: SQLAlchemy
) -> None:
    with client_login(client, manager):
        _comment(client, document, "Aproved.")
        (comment,) = document.__comments__
        kw = {"entity_id": document.id, "object_id": comment.id}
        edited = client.post(
            url_for("comments.edit", **kw),
            data={"body": "Approved.", "__action": "edit"},
        )
        db.session.expire(comment)
        body = comment.body
        deleted = client.post(
            url_for("comments.delete", **kw), data={"__action": "delete"}
        )

    assert edited.status_code == 302
    assert body == "Approved."
    assert deleted.status_code == 302
    db.session.expire(document)
    assert document.__comments__ == []


def test_what_an_action_says_shows_on_the_page_it_leads_to(
    document: Document, manager: User, client: FlaskClient
) -> None:
    """Pages on the design system showed no flashed message: they waited in the
    session for a page that did."""
    edit = url_for(
        "documents.document_edit",
        community_id=document.community.slug,
        doc_id=document.id,
    )
    with client_login(client, manager):
        response = client.post(
            edit, data={"title": "minutes-2026.txt"}, follow_redirects=True
        )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    alerts = [
        part.split("</div>")[0]
        for part in html.split('class="ads-alert ads-tone-success"')[1:]
    ]
    assert any("Document properties successfully edited." in a for a in alerts)


def test_the_readers_page_lists_who_read_it(
    document: Document, manager: User, client: FlaskClient
) -> None:
    _page(client, manager, document)
    url = url_for(
        "documents.document_viewers",
        community_id=document.community.slug,
        doc_id=document.id,
    )
    with client_login(client, manager):
        html = unescape(client.get(url).get_data(as_text=True))

    # The page lists the members who read it, its author aside.
    assert "Read by 0 members" in html
    assert "Nobody has read it yet." in html


def test_everything_in_a_folder_is_a_tree(
    community1: Community,
    manager: User,
    client: FlaskClient,
    db: SQLAlchemy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """From the search index, filled as the objects are saved."""
    monkeypatch.setenv("TESTING_DIRECT_FUNCTION_CALL", "testing")
    ensure_services_started(["indexing"])
    folder = community1.folder.create_subfolder("Minutes")
    folder.create_document(title="2026.txt").set_content(b"one", "text/plain")
    db.session.commit()
    url = url_for(
        "documents.descendants_view",
        community_id=community1.slug,
        folder_id=community1.folder.id,
    )
    with client_login(client, manager):
        response = client.get(url)

    assert response.status_code == 200
    html = unescape(response.get_data(as_text=True))
    assert "Everything in it" in html
    nested = html.split(">Minutes</span>")[1].split("</li>")[0]
    assert 'class="ads-tree ads-tree--nested"' in nested
    assert "2026.txt" in nested


def test_a_reader_has_no_document_mailed_by_the_site(
    community1: Community, document: Document, client: FlaskClient, db: SQLAlchemy
) -> None:
    reader = _member(db, community1, MEMBER)

    with client_login(client, reader), mail.record_messages() as outbox:
        status = _post(
            client,
            "documents.document_send",
            document,
            recipient="anyone@example.org",
            message="Buy now.",
        )

    assert status == 403
    assert outbox == []
