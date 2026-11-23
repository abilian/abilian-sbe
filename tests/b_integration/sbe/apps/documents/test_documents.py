# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import IO, TYPE_CHECKING

import pytest
from dramatiq import Message

from abilian.core.models.subjects import User
from abilian.sbe.apps.documents.models import Document, Folder
from abilian.sbe.apps.documents.tasks import process_document
from abilian.sbe.apps.documents.views.folders import explore_archive
from abilian.services import index_service, security_service
from tests.util import DATA_DIR, login

if TYPE_CHECKING:
    from dramatiq.brokers.stub import StubBroker
    from sqlalchemy.orm import Session

    from abilian.app import Application
    from abilian.sbe.apps.communities.models import Community


def open_file(filename: str) -> IO[bytes]:
    path = DATA_DIR / "documents" / "dummy_files" / filename
    return path.open("rb")


@pytest.fixture
def broker(app: Application) -> StubBroker:
    return process_document.broker


def test_an_unscanned_document_is_queued_for_the_antivirus(
    app: Application,
    session: Session,
    broker: StubBroker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Folder(title="root")
    doc = Document(parent=root, title="test")
    with open_file("onepage.pdf") as fd:
        doc.set_content(fd.read(), "application/pdf")
    session.add(doc)
    session.commit()
    # The commit queues the document's conversions, with an antivirus scan.
    broker.flush_all()
    monkeypatch.setitem(app.config, "ANTIVIRUS_CHECK_REQUIRED", True)

    doc.ensure_antivirus_scheduled()

    queue = broker.queues[process_document.queue_name].queue
    messages = [Message.decode(data) for data in queue]
    assert [(m.actor_name, m.args) for m in messages] == [
        ("process_document", (doc.id,))
    ]


def test_a_document_is_not_queued_when_no_scan_is_required(
    app: Application,
    session: Session,
    broker: StubBroker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = Document(parent=Folder(title="root"), title="test")
    doc.set_content(b"content", "text/plain")
    session.add(doc)
    session.commit()
    # The commit queues the document's conversions, with an antivirus scan.
    broker.flush_all()
    monkeypatch.setitem(app.config, "ANTIVIRUS_CHECK_REQUIRED", False)

    doc.ensure_antivirus_scheduled()

    assert not broker.queues[process_document.queue_name].queue


def test_antivirus_properties(
    app: Application, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Folder(title="root")
    doc = Document(parent=root, title="test")
    doc.set_content(b"content", "text/plain")
    meta = doc.content_blob.meta

    # 1: not check required ################
    # no data in meta
    monkeypatch.setitem(app.config, "ANTIVIRUS_CHECK_REQUIRED", False)
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
    monkeypatch.setitem(app.config, "ANTIVIRUS_CHECK_REQUIRED", True)
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
    monkeypatch,
) -> None:
    monkeypatch.setenv("TESTING_DIRECT_FUNCTION_CALL", "testing")
    index_service.start()
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
        res = svc.search("folder", object_types=obj_types, user=user_no_community)
        assert len(res) == 0

    with login(community1.test_user):
        res = svc.search("folder", object_types=obj_types, user=community1.test_user)
        assert len(res) == 1
        hit = res[0]
        assert hit["object_key"] == folder.object_key
        assert hit["community_slug"] == community1.slug

    with login(community2.test_user):
        res = svc.search("folder", object_types=obj_types, user=community2.test_user)
        assert len(res) == 1
        hit = res[0]
        assert hit["object_key"] == folder_other.object_key
        assert hit["community_slug"] == community2.slug


def test_explore_archive_without_uncompressing_yields_the_upload() -> None:
    with open_file("content.zip") as fd:
        result = [("/".join(path), f) for path, f in explore_archive(fd)]

    assert result == [("", fd)]


def archive_paths(filename: str) -> set[str]:
    with open_file(filename) as fd:
        archive_content = explore_archive(fd, uncompress=True)
        return {f"{'/'.join(path)}/{f.filename}" for path, f in archive_content}


def test_explore_archive_yields_the_files_of_a_zip() -> None:
    assert {
        "existing-doc/file.txt",
        "existing-doc/subfolder_in_renamed/doc.txt",
        "folder 1/doc.txt",
        "folder 1/dos cp437: é.txt",
    } <= archive_paths("content.zip")


def test_explore_archive_decodes_a_utf8_name_without_the_utf8_flag() -> None:
    assert "folder 1/osx: utf-8: é.txt" in archive_paths("content.zip")
