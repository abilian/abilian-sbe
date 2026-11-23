# Copyright (c) 2026, Abilian SAS

"""What the document views make of what a request asks: the types a browser is let
show, the roles a manager may give, the folders things may go to, and the requests
that are the client's error, answered as such rather than with a server error."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING
from uuid import uuid4
from zipfile import ZipFile

import pytest
from flask_login import login_user
from PIL import Image

from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MANAGER, MEMBER
from abilian.services import security_service
from abilian.web.util import url_for
from tests.util import client_login, ensure_services_started

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community
    from abilian.sbe.apps.documents.models import Document, Folder

SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


@pytest.fixture
def manager(community1: Community, db: SQLAlchemy) -> User:
    ensure_services_started(["security"])
    community1.set_membership(community1.test_user, MANAGER)
    db.session.commit()
    return community1.test_user


def _member(db: SQLAlchemy, community: Community, role=MEMBER) -> User:
    user = User(
        email=f"{uuid4().hex}@example.com", password=uuid4().hex, can_login=True
    )
    db.session.add(user)
    db.session.flush()
    community.set_membership(user, role)
    db.session.commit()
    return user


def _folder_url(folder: Folder, endpoint: str = "documents.folder_post") -> str:
    return url_for(endpoint, community_id=folder.community.slug, folder_id=folder.id)


def _doc_url(doc: Document, endpoint: str, **args) -> str:
    return url_for(endpoint, community_id=doc.community.slug, doc_id=doc.id, **args)


def _upload(
    client: FlaskClient, user: User, folder: Folder, content: bytes, name: str, ct: str
) -> Document:
    with client_login(client, user):
        response = client.post(
            _folder_url(folder),
            data={"file": (BytesIO(content), name, ct), "action": "upload"},
        )
    assert response.status_code == 302
    return next(doc for doc in folder.documents if doc.title == name)


def _png() -> bytes:
    out = BytesIO()
    Image.new("RGB", (4, 4), "red").save(out, "PNG")
    return out.getvalue()


#
# What a browser is let show
#
def test_an_svg_is_downloaded_never_shown(
    community1: Community, manager: User, client: FlaskClient
) -> None:
    doc = _upload(client, manager, community1.folder, SVG, "x.svg", "image/svg+xml")

    with client_login(client, manager):
        download = client.get(_doc_url(doc, "documents.document_download"))
        preview = client.get(_doc_url(doc, "documents.document_preview_image"))

    for response in (download, preview):
        assert response.status_code == 200
        assert response.headers["Content-Disposition"].startswith("attachment")
        assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_a_png_is_shown_in_the_browser(
    community1: Community, manager: User, client: FlaskClient
) -> None:
    doc = _upload(client, manager, community1.folder, _png(), "x.png", "image/png")

    with client_login(client, manager):
        response = client.get(_doc_url(doc, "documents.document_download"))

    assert response.status_code == 200
    assert "Content-Disposition" not in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_a_preview_size_that_is_no_number_is_the_default(
    community1: Community, manager: User, client: FlaskClient
) -> None:
    doc = _upload(client, manager, community1.folder, _png(), "x.png", "image/png")

    with client_login(client, manager):
        url = _doc_url(doc, "documents.document_preview_image", size="big")
        response = client.get(url)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/png"


#
# Refreshing a preview
#
def test_refreshing_a_preview_is_a_post(
    community1: Community, manager: User, client: FlaskClient
) -> None:
    doc = _upload(client, manager, community1.folder, b"one", "a.txt", "text/plain")

    with client_login(client, manager):
        response = client.get(_doc_url(doc, "documents.refresh_preview"))

    assert response.status_code == 405


def test_a_reader_refreshing_a_preview_changes_nothing(
    community1: Community,
    manager: User,
    client: FlaskClient,
    db: SQLAlchemy,
) -> None:
    doc = _upload(client, manager, community1.folder, b"one", "a.txt", "text/plain")
    doc.content_type = "application/octet-stream"
    db.session.commit()
    reader = _member(db, community1)

    with client_login(client, reader):
        response = client.post(_doc_url(doc, "documents.refresh_preview"))

    assert response.status_code == 403
    db.session.expire_all()
    assert doc.content_type == "application/octet-stream"


#
# A folder's permissions
#
def test_a_manager_gives_no_role_the_page_does_not_offer(
    community1: Community, manager: User, client: FlaskClient, db: SQLAlchemy
) -> None:
    folder = community1.folder
    other = _member(db, community1)

    with client_login(client, manager):
        response = client.post(
            _folder_url(folder, "documents.permissions_update"),
            data={"action": "add-user-role", "user": other.id, "role": "admin"},
        )

    assert response.status_code == 400
    assert not security_service.has_role(other, "admin")


def test_the_permissions_history_escapes_what_it_tells(
    app: Flask,
    community1: Community,
    manager: User,
    client: FlaskClient,
    db: SQLAlchemy,
) -> None:
    folder = community1.folder.create_subfolder("Board")
    other = _member(db, community1)
    # A role granted before the roles were checked, its name in the history.
    with app.test_request_context():
        login_user(manager)
        security_service.grant_role(other, "<b>boss</b>", folder)
        db.session.commit()

    with client_login(client, manager):
        response = client.get(_folder_url(folder, "documents.permissions"))

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<b>boss</b>" not in html
    assert "&lt;b&gt;boss&lt;/b&gt;" in html


#
# Moving, and the folder's other actions
#
def test_nothing_is_moved_to_another_communitys_folder(
    community1: Community,
    community2: Community,
    manager: User,
    client: FlaskClient,
    db: SQLAlchemy,
) -> None:
    community2.set_membership(manager, MANAGER)
    db.session.commit()
    doc = _upload(client, manager, community1.folder, b"one", "a.txt", "text/plain")
    elsewhere = community2.folder

    with client_login(client, manager):
        response = client.post(
            _folder_url(community1.folder),
            data={
                "action": "move",
                "object-selected": f"cmis:document:{doc.id}",
                "target-folder": elsewhere.id,
            },
        )

    assert response.status_code == 404
    db.session.expire_all()
    assert doc.parent == community1.folder


def test_a_selection_outside_the_folder_is_a_bad_request(
    community1: Community, manager: User, client: FlaskClient, db: SQLAlchemy
) -> None:
    sub = community1.folder.create_subfolder("Sub")
    db.session.commit()
    doc = _upload(client, manager, community1.folder, b"one", "a.txt", "text/plain")

    with client_login(client, manager):
        response = client.post(
            _folder_url(sub),
            data={"action": "delete", "object-selected": f"cmis:document:{doc.id}"},
        )

    assert response.status_code == 400
    db.session.expire_all()
    assert doc.parent == community1.folder


def test_an_unknown_folder_action_is_a_bad_request(
    community1: Community, manager: User, client: FlaskClient
) -> None:
    with client_login(client, manager):
        response = client.post(
            _folder_url(community1.folder), data={"action": "frobnicate"}
        )

    assert response.status_code == 400


def test_checking_a_name_for_an_unknown_action_is_a_bad_request(
    community1: Community, manager: User, client: FlaskClient
) -> None:
    url = url_for(
        "documents.check_valid_name",
        community_id=community1.slug,
        object_id=community1.folder.id,
        action="frobnicate",
        title="x",
    )
    with client_login(client, manager):
        response = client.get(url)

    assert response.status_code == 400


def test_the_view_style_is_changed_by_a_post_only(
    community1: Community, manager: User, client: FlaskClient
) -> None:
    url = _folder_url(community1.folder, "documents.change_view_style")
    with client_login(client, manager):
        response = client.get(url)

    assert response.status_code == 405


#
# What the antivirus has not cleared
#
def _infected(db: SQLAlchemy, doc: Document) -> None:
    doc.content_blob.meta = {**doc.content_blob.meta, "antivirus": False}
    db.session.commit()


def test_an_infected_document_is_neither_downloaded_nor_sent(
    community1: Community, manager: User, client: FlaskClient, db: SQLAlchemy
) -> None:
    doc = _upload(client, manager, community1.folder, b"x", "x.txt", "text/plain")
    _infected(db, doc)

    with client_login(client, manager):
        download = client.get(_doc_url(doc, "documents.document_download"))
        sent = client.post(
            _doc_url(doc, "documents.document_send"),
            data={"recipient": "someone@example.com"},
        )

    assert download.status_code == 403
    assert sent.status_code == 403


def test_a_folder_archive_leaves_an_infected_document_out(
    community1: Community, manager: User, client: FlaskClient, db: SQLAlchemy
) -> None:
    folder = community1.folder
    clean = _upload(client, manager, folder, b"ok", "clean.txt", "text/plain")
    infected = _upload(client, manager, folder, b"x", "infected.txt", "text/plain")
    _infected(db, infected)

    with client_login(client, manager):
        response = client.post(
            _folder_url(folder),
            data={
                "action": "download",
                "object-selected": [
                    f"cmis:document:{clean.id}",
                    f"cmis:document:{infected.id}",
                ],
            },
        )

    assert response.status_code == 200
    names = ZipFile(BytesIO(response.data)).namelist()
    assert "clean.txt" in names
    assert not [name for name in names if name.endswith("infected.txt")]
