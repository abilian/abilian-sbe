# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import uuid
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

from abilian.core.models.blob import Blob
from abilian.services import blob_store, session_blob_store

if TYPE_CHECKING:
    from flask import Flask

    from abilian.core.sqlalchemy import SQLAlchemy


def test_auto_uuid() -> None:
    blob = Blob()
    assert blob.uuid is not None
    assert isinstance(blob.uuid, uuid.UUID)

    # test provided uuid is not replaced by a new one
    u = uuid.UUID("4f80f02f-52e3-4fe2-b9f2-2c3e99449ce9")
    blob = Blob(uuid=u)
    assert isinstance(blob.uuid, uuid.UUID)
    assert blob.uuid, u


def test_meta() -> None:
    blob = Blob()
    assert blob.meta == {}


#
# Integration tests
#
def test_md5(app: Flask, db: SQLAlchemy) -> None:
    blob = Blob("test md5")
    assert "md5" in blob.meta
    assert blob.meta["md5"] == "0e4e3b2681e8931c067a23c583c878d5"


def test_size(app: Flask, db: SQLAlchemy) -> None:
    blob = Blob("test")
    assert blob.size == 4


def test_filename(app: Flask, db: SQLAlchemy) -> None:
    content = StringIO("test")
    content.filename = "test.txt"
    blob = Blob(content)
    assert "filename" in blob.meta
    assert blob.meta["filename"] == "test.txt"


def test_mimetype(app: Flask, db: SQLAlchemy) -> None:
    content = StringIO("test")
    content.content_type = "text/plain"
    blob = Blob(content)
    assert "mimetype" in blob.meta
    assert blob.meta["mimetype"] == "text/plain"


def test_nonzero(app: Flask, db: SQLAlchemy) -> None:
    blob = Blob("test md5")
    assert bool(blob)

    # change uuid: repository will return None for blob.file
    blob.uuid = uuid.uuid4()
    assert not bool(blob)


# def test_query(app, db):
#     session = db.session
#     content = b"content"
#     b = Blob(content)
#     session.add(b)
#     session.flush()
#
#     assert Blob.query.by_uuid(b.uuid) is b
#     assert Blob.query.by_uuid(str(b.uuid)) is b
#
#     u = uuid.uuid4()
#     assert Blob.query.by_uuid(u) is None


def test_value(app: Flask, db: SQLAlchemy) -> None:
    session = db.session
    content = b"content"
    blob = Blob(content)

    tr = session.begin(nested=True)
    session.add(blob)
    tr.commit()

    assert blob_store.get(blob.uuid) is None

    path = session_blob_store.get(blob, blob.uuid)
    assert path
    assert isinstance(path, Path)
    assert path.open("rb").read() == content
    assert blob.value == content

    session.commit()
    path = blob_store.get(blob.uuid)
    assert path
    assert isinstance(path, Path)
    assert path.open("rb").read() == content
    assert blob.value == content

    session.begin(nested=True)  # match session.rollback

    with session.begin(nested=True):
        session.delete(blob)
        # object marked for deletion, but instance attribute should still be
        # readable
        path = session_blob_store.get(blob, blob.uuid)
        assert path
        assert isinstance(path, Path)
        fd = path.open("rb")
        assert fd.read() == content

    # commit in transaction: session_repository has no content, 'physical'
    # repository still has content
    assert session_blob_store.get(blob, blob.uuid) is None
    path = blob_store.get(blob.uuid)
    assert path
    assert isinstance(path, Path)
    assert path.open("rb").read() == content

    # rollback: session_repository has content again
    session.rollback()
    path = session_blob_store.get(blob, blob.uuid)
    assert path
    assert isinstance(path, Path)
    assert path.open("rb").read() == content

    session.delete(blob)
    session.flush()
    assert session_blob_store.get(blob, blob.uuid) is None
    path = blob_store.get(blob.uuid)
    assert path
    assert isinstance(path, Path)
    assert path.open("rb").read() == content

    session.commit()
    assert blob_store.get(blob.uuid) is None
