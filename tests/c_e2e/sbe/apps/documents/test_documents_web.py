# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from io import BytesIO
from typing import IO, TYPE_CHECKING
from zipfile import ZipFile

import flask_mail
import pytest
from flask import g, get_flashed_messages
from PIL import Image
from pytest import fixture
from toolz import first
from werkzeug.datastructures import FileStorage

from abilian.sbe.apps.communities.models import WRITER, Community
from abilian.sbe.apps.communities.presenters import CommunityPresenter
from abilian.sbe.apps.documents.models import Folder
from abilian.sbe.apps.documents.views import util as view_util
from abilian.services import security_service
from abilian.services.conversion.handlers import HAS_PDFTOTEXT
from abilian.services.security import ADMIN, READER
from abilian.web.util import url_for
from tests.util import DATA_DIR, client_login, path_from_url

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy


def open_file(filename: str) -> IO[bytes]:
    path = DATA_DIR / "documents" / "dummy_files" / filename
    return path.open("rb")


def uid_from_url(url):
    return int(url.split("/")[-1])


@fixture
def community(community1: Community, db: SQLAlchemy) -> Community:
    community = community1
    user = community.test_user
    root_folder = Folder(title="root")
    db.session.add(root_folder)
    db.session.flush()

    community.type = "participative"
    community.set_membership(user, WRITER)
    db.session.commit()

    return community


def test_util_create(
    app: Application, client: FlaskClient, db: SQLAlchemy, community: Community
) -> None:
    folder = community.folder
    user = community.test_user

    with client_login(client, user):
        g.community = CommunityPresenter(community)
        name = "document"
        fs = FileStorage(BytesIO(b"content"), filename=name, content_type="text/plain")

        doc = view_util.create_document(user, folder, fs)
        db.session.flush()
        assert doc.parent == folder
        assert doc.name == name

        # test upload with same name: should be renamed
        fs = FileStorage(BytesIO(b"content"), filename=name, content_type="text/plain")
        doc2 = view_util.create_document(user, folder, fs)
        db.session.flush()
        assert doc2.parent == folder
        assert len(folder.children) == 2
        assert doc2.name == f"{name}-1"

        messages = get_flashed_messages()
        assert len(messages) == 1


def test_home(
    app: Application, client: FlaskClient, db: SQLAlchemy, community: Community
) -> None:
    folder = community.folder
    user = community.test_user

    with client_login(client, user):
        response = client.get(url_for("documents.index", community_id=community.slug))
        assert response.status_code == 302
        path = path_from_url(response.location)
        expected = f"/communities/{community.slug}/docs/folder/{folder.id}"
        assert path == expected


def test_content_outside_the_community_is_not_found(
    client: FlaskClient,
    db: SQLAlchemy,
    community: Community,
    community2: Community,
) -> None:
    user = community.test_user
    # A member of both: the answer cannot come from access rights.
    community2.set_membership(user, WRITER)
    other_doc = community2.folder.create_document("other")
    db.session.commit()
    repository_root = Folder.query.filter(Folder._parent_id.is_(None)).first()
    assert repository_root.community is None

    urls = [
        url_for(endpoint, community_id=community.slug, folder_id=folder.id)
        for folder in (community2.folder, repository_root)
        for endpoint in ("documents.folder_view", "documents.folder_json")
    ]
    urls.append(
        url_for(
            "documents.document_view", community_id=community.slug, doc_id=other_doc.id
        )
    )
    with client_login(client, user):
        for url in urls:
            assert client.get(url).status_code == 404, url


def test_role_form_with_a_missing_field_is_a_bad_request(
    app: Application, client: FlaskClient, db: SQLAlchemy, community: Community
) -> None:
    # Answer as in production: in debug mode, Flask raises the error instead.
    app.config["TRAP_BAD_REQUEST_ERRORS"] = False
    security_service.start()
    user = community.test_user
    security_service.grant_role(user, ADMIN)
    db.session.commit()
    folder = community.folder
    url = url_for(
        "documents.permissions_update", community_id=community.slug, folder_id=folder.id
    )
    incomplete_forms = [
        {"action": "add-user-role", "user": user.id},
        {"action": "add-user-role", "role": "reader"},
        {"action": "add-group-role", "group": 1},
        {"action": "add-group-role", "role": "reader"},
    ]

    with client_login(client, user):
        for data in incomplete_forms:
            assert client.post(url, data=data).status_code == 400, data


@pytest.mark.parametrize(
    "data",
    [
        {"action": "add-user-role", "role": "reader", "user": 999999},
        {"action": "add-group-role", "role": "reader", "group": 999999},
        # The delete buttons: their name is the action, their value role:id.
        {"delete-user-role": "reader:999999"},
        {"delete-group-role": "reader:999999"},
    ],
)
def test_a_role_form_for_an_unknown_principal_is_not_found(
    data: dict,
    client: FlaskClient,
    db: SQLAlchemy,
    community: Community,
) -> None:
    security_service.start()
    user = community.test_user
    security_service.grant_role(user, ADMIN)
    db.session.commit()
    url = url_for(
        "documents.permissions_update",
        community_id=community.slug,
        folder_id=community.folder.id,
    )

    with client_login(client, user):
        assert client.post(url, data=data).status_code == 404


def test_a_manager_removes_a_role_on_a_folder(
    client: FlaskClient, db: SQLAlchemy, community: Community, community2: Community
) -> None:
    security_service.start()
    user = community.test_user
    security_service.grant_role(user, ADMIN)
    other = community2.test_user
    folder = community.folder
    security_service.grant_role(other, READER, folder)
    db.session.commit()
    url = url_for(
        "documents.permissions_update", community_id=community.slug, folder_id=folder.id
    )

    with client_login(client, user):
        response = client.post(url, data={"delete-user-role": f"reader:{other.id}"})

    assert response.status_code == 302
    assert not security_service.has_role(other, READER, folder)


def test_changing_to_an_unknown_owner_keeps_the_owner(
    app: Application, client: FlaskClient, db: SQLAlchemy, community: Community
) -> None:
    security_service.start()
    user = community.test_user
    security_service.grant_role(user, ADMIN)
    folder = community.folder
    doc = folder.create_document("owned")
    doc.owner = user
    db.session.commit()
    url = url_for(
        "documents.folder_post", community_id=community.slug, folder_id=folder.id
    )
    data = {
        "action": "change-owner",
        "new_owner": 999999,
        "object-selected": [f"cmis:document:{doc.id:d}"],
    }

    with client_login(client, user):
        assert client.post(url, data=data).status_code == 404

    db.session.expire_all()
    assert doc.owner == user


def test_name_check_without_an_object_is_a_bad_request(
    app: Application, client: FlaskClient, community: Community
) -> None:
    # Answer as in production: in debug mode, Flask raises the error instead.
    app.config["TRAP_BAD_REQUEST_ERRORS"] = False
    url = url_for("documents.check_valid_name", community_id=community.slug)
    with client_login(client, community.test_user):
        response = client.get(url, query_string={"action": "new", "title": "x"})

    assert response.status_code == 400


def test_name_check_tells_a_taken_name_from_a_free_one(
    app: Application, db: SQLAlchemy, client: FlaskClient, community: Community
) -> None:
    security_service.start()
    user = community.test_user
    security_service.grant_role(user, ADMIN)
    folder = community.folder
    folder.create_document("taken")
    db.session.commit()
    url = url_for("documents.check_valid_name", community_id=community.slug)

    with client_login(client, user):
        for title, valid in (("taken", False), ("free", True)):
            query = {"action": "new", "object_id": folder.id, "title": title}
            response = client.get(url, query_string=query)
            assert response.get_json()["valid"] is valid, title


def _test_upload(
    community: Community,
    client: FlaskClient,
    title: str,
    content_type: str,
    test_preview: bool = True,
    assert_preview_available: bool = True,
) -> None:
    data = {"file": (open_file(title), title, content_type), "action": "upload"}

    folder = community.folder
    url = url_for(
        "documents.folder_post", community_id=community.slug, folder_id=folder.id
    )
    response = client.post(url, data=data)
    assert response.status_code == 302

    doc = folder.children[0]
    assert doc.title == title

    url = url_for("documents.document_view", community_id=community.slug, doc_id=doc.id)
    response = client.get(url)
    assert response.status_code == 200

    url = url_for(
        "documents.document_download", community_id=community.slug, doc_id=doc.id
    )
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == content_type

    content = open_file(title).read()
    assert response.data == content

    if test_preview:
        url = url_for(
            "documents.document_preview_image",
            community_id=community.slug,
            doc_id=doc.id,
            size=500,
        )
        response = client.get(url)
        if assert_preview_available:
            assert response.status_code == 200
            assert response.headers["Content-Type"] == "image/jpeg"
        else:
            # redirect to 'missing image'
            assert response.status_code == 302
            assert response.headers["Cache-Control"] == "no-cache"

    url = url_for(
        "documents.document_delete", community_id=community.slug, doc_id=doc.id
    )
    response = client.post(url)
    assert response.status_code == 302

    url = url_for("documents.document_view", community_id=community.slug, doc_id=doc.id)
    response = client.get(url)
    assert response.status_code == 404


def test_text_upload(client: FlaskClient, community: Community) -> None:
    name = "wikipedia-fr.txt"
    user = community.test_user
    with client_login(client, user):
        _test_upload(community, client, name, "text/plain", test_preview=False)


def test_pdf_upload(client: FlaskClient, community: Community) -> None:
    name = "onepage.pdf"
    user = community.test_user
    with client_login(client, user):
        # The preview is rendered by poppler, which CI images may lack.
        _test_upload(
            community,
            client,
            name,
            "application/pdf",
            assert_preview_available=HAS_PDFTOTEXT,
        )


def test_image_upload(client: FlaskClient, community: Community) -> None:
    name = "picture.jpg"
    user = community.test_user
    with client_login(client, user):
        _test_upload(community, client, name, "image/jpeg")


def test_the_preview_of_a_png_says_it_is_a_png(
    client: FlaskClient, community: Community
) -> None:
    """It used to say image/jpeg, whatever the format it actually carried."""
    png = BytesIO()
    Image.new("RGB", (800, 600), "red").save(png, "PNG")
    png.seek(0)
    folder = community.folder

    with client_login(client, community.test_user):
        client.post(
            url_for(
                "documents.folder_post",
                community_id=community.slug,
                folder_id=folder.id,
            ),
            data={"file": (png, "red.png", "image/png"), "action": "upload"},
        )
        response = client.get(
            url_for(
                "documents.document_preview_image",
                community_id=community.slug,
                doc_id=folder.children[0].id,
                size=500,
            )
        )

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/png"
    assert response.data.startswith(b"\x89PNG")


def test_preview_of_an_image_whose_blob_file_is_gone(
    client: FlaskClient, community: Community
) -> None:
    """A Blob row can outlive its file -- a restore without the file store.

    `Blob.value` is None then, and the image branch of the preview view handed
    that straight to resize(), which 500ed on `None.read()`. The view has a
    missing-preview image for exactly this case; it just never reached it.
    """
    name = "picture.jpg"
    user = community.test_user

    with client_login(client, user):
        data = {"file": (open_file(name), name, "image/jpeg"), "action": "upload"}
        url = url_for(
            "documents.folder_post",
            community_id=community.slug,
            folder_id=community.folder.id,
        )
        assert client.post(url, data=data).status_code == 302

        doc = community.folder.children[0]
        doc.content_blob.file.unlink()
        assert doc.content is None

        url = url_for(
            "documents.document_preview_image",
            community_id=community.slug,
            doc_id=doc.id,
            size=500,
        )
        response = client.get(url)

    assert response.status_code == 302
    assert response.headers["Cache-Control"] == "no-cache"


def test_binary_upload(client, community) -> None:
    name = "random.bin"
    user = community.test_user
    with client_login(client, user):
        _test_upload(
            community,
            client,
            name,
            "application/octet-stream",
            assert_preview_available=False,
        )


def test_zip_upload_uncompress(
    community: Community, db: SQLAlchemy, client: FlaskClient
) -> None:
    subfolder = Folder(title="folder 1", parent=community.folder)
    db.session.add(subfolder)
    db.session.flush()

    folder = community.folder
    files = [
        (BytesIO(b"A document"), "existing-doc", "text/plain"),
        (open_file("content.zip"), "content.zip", "application/zip"),
    ]
    data = {"file": files, "action": "upload", "uncompress_files": True}
    url = url_for(
        "documents.folder_post", community_id=community.slug, folder_id=folder.id
    )
    user = community.test_user
    with client_login(client, user):
        response = client.post(url, data=data)

    assert response.status_code == 302

    expected = {"existing-doc", "folder 1", "existing-doc-1"}
    assert expected == {f.title for f in folder.children}

    expected = {"folder 1", "existing-doc-1"}
    assert expected == {f.title for f in folder.subfolders}


def test_zip(community: Community, client: FlaskClient) -> None:
    user = community.test_user
    with client_login(client, user):
        title = "onepage.pdf"
        content_type = "application/pdf"
        data = {"file": (open_file(title), title, content_type), "action": "upload"}
        folder = community.folder
        url = url_for(
            "documents.folder_post", community_id=community.slug, folder_id=folder.id
        )
        response = client.post(url, data=data)
        assert response.status_code == 302

        doc = folder.children[0]
        data = {"action": "download", "object-selected": [f"cmis:document:{doc.id:d}"]}
        url = url_for(
            "documents.folder_post", community_id=community.slug, folder_id=folder.id
        )
        response = client.post(url, data=data)
        assert response.status_code == 200
        assert response.content_type == "application/zip"

        zipfile = ZipFile(BytesIO(response.data))
        assert [zipfile.namelist()[0]] == [title]


def test_recursive_zip(community: Community, client: FlaskClient) -> None:
    user = community.test_user
    with client_login(client, user):
        data1 = {"action": "new", "title": "my folder"}
        folder = community.folder
        url = url_for(
            "documents.folder_post", community_id=community.slug, folder_id=folder.id
        )
        response = client.post(url, data=data1)
        assert response.status_code == 302

        my_folder = folder.children[0]

        title = "onepage.pdf"
        content_type = "application/pdf"
        data2 = {"file": (open_file(title), title, content_type), "action": "upload"}
        url = url_for(
            "documents.folder_post", community_id=community.slug, folder_id=my_folder.id
        )
        response = client.post(url, data=data2)
        assert response.status_code == 302

        data3 = {
            "action": "download",
            "object-selected": [f"cmis:folder:{my_folder.id:d}"],
        }
        url = url_for(
            "documents.folder_post", community_id=community.slug, folder_id=folder.id
        )
        response = client.post(url, data=data3)
        assert response.status_code == 200
        assert response.content_type == "application/zip"

        zipfile = ZipFile(BytesIO(response.data))
        assert zipfile.namelist() == [f"my folder/{title}"]


def test_document_send_by_mail(
    app: Application, community: Community, client: FlaskClient
) -> None:
    mail = app.extensions["mail"]
    folder = community.folder
    user = community.test_user
    with client_login(client, user):
        # upload files
        for filename in ("ascii title.txt", "utf-8 est arrivé!.txt"):
            content_type = "text/plain"
            data = {
                "file": (BytesIO(b"file content"), filename, content_type),
                "action": "upload",
            }
            url = url_for(
                "documents.folder_post",
                community_id=community.slug,
                folder_id=folder.id,
            )
            client.post(url, data=data)

        ascii_doc = folder.children[0]
        unicode_doc = folder.children[1]

        def get_send_url(doc_id: int) -> str:
            return url_for(
                "documents.document_send", community_id=community.slug, doc_id=doc_id
            )

        # mail ascii filename
        with mail.record_messages() as outbox:
            url = get_send_url(ascii_doc.id)
            response = client.post(
                url,
                data={"recipient": "dest@example.com", "message": "Voilà un fichier"},
            )
            assert response.status_code == 302
            assert len(outbox) == 1

            msg = outbox[0]
            assert msg.subject == "[Abilian Test] Unknown sent you a file"
            assert msg.recipients == ["dest@example.com"]

            assert len(msg.attachments) == 1

            attachment = first(msg.attachments)
            assert isinstance(attachment, flask_mail.Attachment)
            assert attachment.filename == "ascii title.txt"

        # mail unicode filename
        with mail.record_messages() as outbox:
            url = get_send_url(unicode_doc.id)
            response = client.post(
                url,
                data={"recipient": "dest@example.com", "message": "Voilà un fichier"},
            )
            assert response.status_code == 302
            assert len(outbox) == 1

            msg = outbox[0]
            assert isinstance(msg, flask_mail.Message)
            assert msg.subject == "[Abilian Test] Unknown sent you a file"
            assert msg.recipients == ["dest@example.com"]
            assert len(msg.attachments) == 1

            attachment = first(msg.attachments)
            assert isinstance(attachment, flask_mail.Attachment)
            assert attachment.filename == "utf-8 est arrivé!.txt"
