# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from pytest import raises

from abilian.services.blob_store import blob_store

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

UUID_STR = "4f80f02f-52e3-4fe2-b9f2-2c3e99449ce9"
UUID = uuid.UUID(UUID_STR)


def test_rel_path(session: Session) -> None:
    p = blob_store.rel_path(UUID)
    expected = Path("4f", "80", "4f80f02f-52e3-4fe2-b9f2-2c3e99449ce9")
    assert isinstance(p, Path)
    assert p == expected


def test_abs_path(session: Session) -> None:
    p = blob_store.abs_path(UUID)
    assert isinstance(p, Path)

    # FIXME: fails on a Mac due to symlinks /var@ -> /private/var
    # expected = Path(self.app.instance_path, 'data', 'files',
    #                 '4f', '80', '4f80f02f-52e3-4fe2-b9f2-2c3e99449ce9')
    # self.assertEquals(p, expected)


def test_get_with_some_content(session: Session) -> None:
    p = blob_store.abs_path(UUID)
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.open("wb").write(b"my file content")

    val = blob_store.get(UUID)
    assert val == p
    assert val.open("rb").read() == b"my file content"

    # __getitem__
    val = blob_store[UUID]
    assert val == p
    assert val.open("rb").read() == b"my file content"


def test_get_with_non_existing_content(session: Session) -> None:
    # non-existent
    u = uuid.UUID("bcdc32ac-498d-4544-9e7f-fb2c75097011")
    default_path = Path("/xxx/default-path")
    assert blob_store.get(u) is None
    assert blob_store.get(u, default=default_path) is default_path

    # __getitem__ non-existent
    with raises(KeyError):
        assert blob_store[u]


def test_set(session: Session) -> None:
    u1 = uuid.uuid4()
    p = blob_store.abs_path(u1)
    blob_store.set(u1, b"my file content")
    assert p.open("rb").read() == b"my file content"


def test_setitem(session: Session) -> None:
    u1 = uuid.uuid4()
    p = blob_store.abs_path(u1)
    blob_store[u1] = b"my file content"
    assert p.open("rb").read() == b"my file content"
    # FIXME: test Unicode content


def test_delete(session: Session) -> None:
    u1 = uuid.uuid4()
    blob_store.set(u1, b"my file content")
    p = blob_store.abs_path(u1)
    assert p.exists()

    blob_store.delete(u1)
    assert not p.exists()


def test_delitem(session: Session) -> None:
    u1 = uuid.uuid4()
    blob_store.set(u1, b"my file content")
    p = blob_store.abs_path(u1)
    assert p.exists()

    del blob_store[u1]
    assert not p.exists()


def test_delete_non_existent(session: Session) -> None:
    # non-existent
    u1 = uuid.uuid4()
    with raises(KeyError):
        blob_store.delete(u1)

    # same w/ __delitem__
    with raises(KeyError):
        del blob_store[u1]
