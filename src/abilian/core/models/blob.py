# Copyright (c) 2012-2024, Abilian SAS

"""Blob.

References to files stored in a on-disk repository
"""

from __future__ import annotations

import hashlib
import uuid
from typing import IO, TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.event import listens_for
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Integer

from abilian.core.models.base import Model
from abilian.core.sqlalchemy import UUID, JSONDict

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm.session import Session
    from sqlalchemy.orm.unitofwork import UOWTransaction


class Blob(Model):
    """Model for storing large file content.

    Files are stored on-disk, named after their uuid. Repository is
    located in instance folder/data/files.
    """

    __tablename__ = "blob"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(), unique=True, nullable=False, default=uuid.uuid4
    )
    meta: Mapped[dict] = mapped_column(JSONDict(), nullable=False, default=dict)

    def __init__(self, value=None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.uuid is None:
            self.uuid = uuid.uuid4()

        if self.meta is None:
            self.meta = {}

        if value is not None:
            self.value = value

    def _md5_hexdigest(self) -> str:
        """Return md5.hexdigest() of self.value."""
        if isinstance(self.value, str):
            content = self.value.encode("utf-8")
        else:
            content = self.value
        return hashlib.md5(content).hexdigest()  # noqa: S324

    @property
    def file(self) -> Path | None:
        """Return :class:`pathlib.Path` object used for storing value."""
        from abilian.services.blob_store import session_blob_store

        return session_blob_store.get(self, self.uuid)

    @property
    def size(self) -> int:
        """Return size in bytes of value."""
        file = self.file
        if file is None:
            return 0
        return file.stat().st_size

    @property
    def value(self) -> bytes | None:
        """Binary value content."""
        file = self.file
        if file is None:
            return None
        return file.read_bytes()

    @value.setter
    def value(self, value: bytes | str | IO) -> None:
        """Store binary content to the repository and update
        `self.meta['md5']`.

        :param:content: bytes, or any object with a `read()` method
        :param:encoding: encoding to use when content is Unicode
        """
        from abilian.services.blob_store import session_blob_store

        session_blob_store.set(self, self.uuid, value)

        if self.value:
            self.meta["md5"] = self._md5_hexdigest()

        filename = getattr(value, "filename", None)
        if filename:
            if isinstance(filename, bytes):
                filename = filename.decode("utf-8")
            self.meta["filename"] = filename

        content_type = getattr(value, "content_type", None)
        if content_type:
            self.meta["mimetype"] = content_type

    @value.deleter
    def value(self) -> None:
        """Remove value from repository."""
        from abilian.services.blob_store import session_blob_store

        session_blob_store.delete(self, self.uuid)

    @property
    def md5(self) -> str | None:
        """Return md5 from meta, or compute it if absent."""
        md5 = self.meta.get("md5")
        if md5 is None and self.value:
            md5 = self._md5_hexdigest()

        return md5

    def __bool__(self) -> bool:
        """A blob is considered falsy if it has no file."""
        return self.file is not None and self.file.exists()

    # Py3k compat
    __nonzero__ = __bool__


@listens_for(sa.orm.Session, "after_flush")
def _blob_propagate_delete_content(
    session: Session, flush_context: UOWTransaction
) -> None:
    deleted = (obj for obj in session.deleted if isinstance(obj, Blob))
    for blob in deleted:
        del blob.value
