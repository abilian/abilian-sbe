from io import BytesIO
from pathlib import Path
from typing import IO
from zipfile import ZipFile

import flask_mail
import pytest
from flask import g, get_flashed_messages
from flask.ctx import RequestContext
from flask.testing import FlaskClient
from pytest import fixture
from toolz import first
from werkzeug.datastructures import FileStorage

from abilian.core.sqlalchemy import SQLAlchemy
from abilian.sbe.app import Application
from abilian.sbe.apps.communities.models import WRITER, Community
from abilian.sbe.apps.communities.presenters import CommunityPresenter
from abilian.sbe.apps.documents.models import Folder
from abilian.sbe.apps.documents.views import util as view_util
from abilian.testing.util import client_login, path_from_url
from abilian.web.util import url_for


def open_file(filename: str) -> IO[bytes]:
    path = Path(__file__).parent / "data" / "dummy_files" / filename
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
    app: Application,
    client: FlaskClient,
    db: SQLAlchemy,
    community: Community,
    req_ctx: RequestContext,
) -> None:
    folder = community.folder
    user = community.test_user

    with client_login(client, user):
        g.community = CommunityPresenter(community)
        name = "document"
        fs = FileStorage(BytesIO(b"content"), filename=name, content_type="text/plain")

        doc = view_util.create_document(folder, fs)
        db.session.flush()
        assert doc.parent == folder
        assert doc.name == name

        # test upload with same name: should be renamed
        fs = FileStorage(BytesIO(b"content"), filename=name, content_type="text/plain")
        doc2 = view_util.create_document(folder, fs)
        db.session.flush()
        assert doc2.parent == folder
        assert len(folder.children) == 2
        assert doc2.name == name + "-1"

        messages = get_flashed_messages()
        assert len(messages) == 1


def test_home(
    app: Application,
    client: FlaskClient,
    db: SQLAlchemy,
    community: Community,
    req_ctx: RequestContext,
) -> None:
    folder = community.folder
    user = community.test_user

    with client_login(client, user):
        response = client.get(url_for("documents.index", community_id=community.slug))
        assert response.status_code == 302
        path = path_from_url(response.location)
        expected = f"/communities/{community.slug}/docs/folder/{folder.id}"
        assert path == expected


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


def test_text_upload(
    client: FlaskClient, community: Community, req_ctx: RequestContext
) -> None:
    name = "wikipedia-fr.txt"
    user = community.test_user
    with client_login(client, user):
        _test_upload(community, client, name, "text/plain", test_preview=False)


def test_pdf_upload(
    client: FlaskClient, community: Community, req_ctx: RequestContext
) -> None:
    name = "onepage.pdf"
    user = community.test_user
    with client_login(client, user):
        _test_upload(community, client, name, "application/pdf")


def test_image_upload(
    client: FlaskClient, community: Community, req_ctx: RequestContext
) -> None:
    name = "picture.jpg"
    user = community.test_user
    with client_login(client, user):
        _test_upload(community, client, name, "image/jpeg")


@pytest.mark.skip()  # FIXME: magic detection mismatch?
def test_binary_upload(client, community, req_ctx):
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
    community: Community, db: SQLAlchemy, client: FlaskClient, req_ctx: RequestContext
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


def test_zip(
    community: Community, client: FlaskClient, req_ctx: RequestContext
) -> None:
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


def test_recursive_zip(
    community: Community, client: FlaskClient, req_ctx: RequestContext
) -> None:
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
        assert zipfile.namelist() == ["my folder/" + title]


def test_document_send_by_mail(
    app: Application, community: Community, client: FlaskClient, req_ctx: RequestContext
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
