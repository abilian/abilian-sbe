import sys
from pathlib import Path
from typing import IO

import pytest
from flask.ctx import RequestContext
from sqlalchemy.orm import Session

from abilian.core.models.subjects import User
from abilian.sbe.app import Application
from abilian.sbe.apps.communities.models import Community
from abilian.sbe.apps.documents.models import Document, Folder
from abilian.sbe.apps.documents.views.folders import explore_archive
from abilian.testing.util import login


def open_file(filename: str) -> IO[bytes]:
    path = Path(__file__).parent / "data" / "dummy_files" / filename
    return path.open("rb")


def test_document(app: Application, session: Session, req_ctx: RequestContext) -> None:
    root = Folder(title="root")
    doc = Document(parent=root, title="test")
    data = open_file("onepage.pdf").read()
    doc.set_content(data, "application/pdf")
    session.add(doc)
    session.commit()

    # coverage
    app.config["ANTIVIRUS_CHECK_REQUIRED"] = True
    doc.ensure_antivirus_scheduled()


def test_antivirus_properties(
    app: Application, session: Session, req_ctx: RequestContext
) -> None:
    root = Folder(title="root")
    doc = Document(parent=root, title="test")
    doc.set_content(b"content", "text/plain")
    appcfg = app.config
    meta = doc.content_blob.meta

    # 1: not check required ################
    # no data in meta
    appcfg["ANTIVIRUS_CHECK_REQUIRED"] = False
    assert doc.antivirus_scanned is False
    assert doc.antivirus_status is None
    assert doc.antivirus_required is False
    assert doc.antivirus_ok is True

    # antivirus was run, but no result
    meta["antivirus"] = None
    assert doc.antivirus_scanned is True
    assert doc.antivirus_status is None
    assert doc.antivirus_required is False
    assert doc.antivirus_ok is True

    # virus detected
    meta["antivirus"] = False
    assert doc.antivirus_scanned is True
    assert doc.antivirus_status is False
    assert doc.antivirus_required is False
    assert doc.antivirus_ok is False

    # virus free
    meta["antivirus"] = True
    assert doc.antivirus_scanned is True
    assert doc.antivirus_status is True
    assert doc.antivirus_required is False
    assert doc.antivirus_ok is True

    # 2: check required ##################
    # no data in meta
    del meta["antivirus"]
    appcfg["ANTIVIRUS_CHECK_REQUIRED"] = True
    assert doc.antivirus_scanned is False
    assert doc.antivirus_status is None
    assert doc.antivirus_required is True
    assert doc.antivirus_ok is False

    # antivirus was run, but no result
    meta["antivirus"] = None
    assert doc.antivirus_scanned is True
    assert doc.antivirus_status is None
    assert doc.antivirus_required is True
    assert doc.antivirus_ok is False

    # virus detected
    meta["antivirus"] = False
    assert doc.antivirus_scanned is True
    assert doc.antivirus_status is False
    assert doc.antivirus_required is False
    assert doc.antivirus_ok is False

    # virus free
    meta["antivirus"] = True
    assert doc.antivirus_scanned is True
    assert doc.antivirus_status is True
    assert doc.antivirus_required is False
    assert doc.antivirus_ok is True


def test_folder_indexed(
    app: Application,
    session: Session,
    community1: Community,
    community2: Community,
    req_ctx: RequestContext,
) -> None:
    index_service = app.services["indexing"]
    index_service.start()

    security_service = app.services["security"]
    security_service.start()

    folder = Folder(title="Folder 1", parent=community1.folder)
    session.add(folder)

    folder_other = Folder(title="Folder 2: other", parent=community2.folder)
    session.add(folder_other)

    user_no_community = User(email="no_community@example.com", can_login=True)
    session.add(user_no_community)

    session.commit()

    svc = index_service
    obj_types = (Folder.entity_type,)

    with login(user_no_community):
        res = svc.search("folder", object_types=obj_types)
        assert len(res) == 0

    with login(community1.test_user):
        res = svc.search("folder", object_types=obj_types)
        assert len(res) == 1
        hit = res[0]
        assert hit["object_key"] == folder.object_key
        assert hit["community_slug"] == community1.slug

    with login(community2.test_user):
        res = svc.search("folder", object_types=obj_types)
        assert len(res) == 1
        hit = res[0]
        assert hit["object_key"] == folder_other.object_key
        assert hit["community_slug"] == community2.slug


@pytest.mark.skipif(sys.version_info >= (3, 0), reason="Doesn't work yet on Py3k")
def test_explore_archive():
    fd = open_file("content.zip")
    result = [("/".join(path), f) for path, f in explore_archive(fd)]
    assert result == [("", fd)]

    fd = open_file("content.zip")
    archive_content = explore_archive(fd, uncompress=True)
    result = {"/".join(path) + "/" + f.filename for path, f in archive_content}
    assert result == {
        "existing-doc/file.txt",
        "existing-doc/subfolder_in_renamed/doc.txt",
        "folder 1/doc.txt",
        "folder 1/dos cp437: é.txt",
        "folder 1/osx: utf-8: é.txt",
    }
