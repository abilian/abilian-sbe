# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import contextlib
import shutil
import typing
import weakref
from pathlib import Path
from typing import IO, Any
from uuid import UUID, uuid1

import sqlalchemy as sa
from flask import g

# import sqlalchemy.event
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm.session import Session, SessionTransaction

from abilian.core.extensions import db
from abilian.services import Service, ServiceState

if typing.TYPE_CHECKING:
    from sqlalchemy.engine.base import Connection
    from sqlalchemy.orm.unitofwork import UOWTransaction

    from abilian.app import Application
    from abilian.core.models import Model
    from abilian.core.models.blob import Blob

_NULL_MARK = object()


def _assert_uuid(uuid: Any) -> None:
    if not isinstance(uuid, UUID):
        msg = "Not an uuid.UUID instance"
        raise TypeError(msg, uuid)


class BlobStoreServiceState(ServiceState):
    #: :class:`Path` path to application repository
    path: Path | None = None


class BlobStoreService(Service):
    """Service for storage of binary objects referenced in database."""

    name = "blob_store"
    AppStateClass = BlobStoreServiceState

    def init_app(self, app: Application) -> None:
        super().init_app(app)

        path = app.data_dir / "files"
        if not path.exists():
            path.mkdir(mode=0o775, parents=True)

        with app.app_context():
            self.app_state.path = path.resolve()

    # data management: paths and accessors
    def rel_path(self, uuid: UUID) -> Path:
        """Contruct relative path from blob store top directory to the file
        named after this uuid.

        :param:uuid: :class:`UUID` instance
        """
        _assert_uuid(uuid)

        filename = str(uuid)
        return Path(filename[0:2], filename[2:4], filename)

    def abs_path(self, uuid: UUID) -> Path:
        """Return absolute :class:`Path` object for given uuid.

        :param:uuid: :class:`UUID` instance
        """
        _assert_uuid(uuid)

        top = self.app_state.path
        rel_path = self.rel_path(uuid)
        dest = top / rel_path
        assert top in dest.parents
        return dest

    def get(self, uuid: UUID, default: Path | None = None) -> Path | None:
        """Return absolute :class:`Path` object for given uuid, if this uuid
        exists in blob store, or `default` if it doesn't.

        :param:uuid: :class:`UUID` instance
        """
        _assert_uuid(uuid)

        path = self.abs_path(uuid)
        if not path.exists():
            return default
        return path

    def set(self, uuid: UUID, content: Any, encoding: str | None = "utf-8") -> None:
        """Store binary content with uuid as key.

        :param:uuid: :class:`UUID` instance
        :param:content: string, bytes, or any object with a `read()` method
        :param:encoding: encoding to use when content is Unicode
        """
        _assert_uuid(uuid)

        dest = self.abs_path(uuid)
        if not dest.parent.exists():
            dest.parent.mkdir(0o775, parents=True)

        if hasattr(content, "read"):
            content = content.read()

        mode = "tw"
        if not isinstance(content, str):
            mode = "bw"
            encoding = None

        with dest.open(mode, encoding=encoding) as file:
            file.write(content)

    def delete(self, uuid: UUID) -> None:
        """Delete file with given uuid.

        :param:uuid: :class:`UUID` instance
        :raises:KeyError if file does not exists
        """
        _assert_uuid(uuid)

        dest = self.abs_path(uuid)
        if not dest.exists():
            msg = "No file can be found for this uuid"
            raise KeyError(msg, uuid)

        dest.unlink()

    def __getitem__(self, uuid: UUID) -> Path:
        _assert_uuid(uuid)

        value = self.get(uuid)
        if value is None:
            msg = "No file can be found for this uuid"
            raise KeyError(msg, uuid)
        return value

    def __setitem__(self, uuid: UUID, content: Any) -> None:
        _assert_uuid(uuid)

        self.set(uuid, content)

    def __delitem__(self, uuid: UUID) -> None:
        _assert_uuid(uuid)

        self.delete(uuid)


blob_store = BlobStoreService()


class SessionBlobStoreState(ServiceState):
    path: Path

    @staticmethod
    def actual_session(session: Session | scoped_session) -> Session:
        if isinstance(session, scoped_session):
            return session()
        return session

    def transaction_key(self, session: Session | scoped_session) -> str:
        session_id = id(self.actual_session(session))
        return f"blob_session_{session_id}"

    # transaction <-> db session accessors
    def get_transaction(
        self, session: Session | scoped_session
    ) -> BlobStoreTransaction | None:
        session = self.actual_session(session)
        key = self.transaction_key(session)
        default = weakref.ref(session), None
        session_reference, transaction = g.get(key, default)
        found_session = session_reference()

        if found_session is None or found_session is not session:
            # old session with same id, maybe not yet garbage collected
            transaction = None
        return transaction

    def set_transaction(
        self,
        session: Session | scoped_session,
        transaction: BlobStoreTransaction | None,
    ) -> None:
        session = self.actual_session(session)
        key = self.transaction_key(session)
        value = (weakref.ref(session), transaction)
        setattr(g, key, value)

    def create_transaction(self, session: Session) -> None:
        if not self.running:
            return

        parent_transaction = self.get_transaction(session)
        transaction = BlobStoreTransaction(self.path, parent_transaction)
        self.set_transaction(session, transaction)

    def end_transaction(self, session: Session) -> None:
        if not self.running:
            return

        transaction = self.get_transaction(session)
        if transaction is not None:
            if not transaction.cleared:
                # root and nested transactions emit "commit", but
                # subtransactions don't
                transaction.commit()
            self.set_transaction(session, transaction._parent)

    def begin(self, session: Session) -> None:
        if not self.running:
            return

        transaction = self.get_transaction(session)
        if transaction is None:
            # FIXME: return or create a new one?
            return

        transaction.begin()

    def commit(self, session: Session) -> None:
        if not self.running:
            return

        transaction = self.get_transaction(session)
        if transaction is None:
            return

        transaction.commit()

    def flush(self, session: Session) -> None:
        # def flush(self, session: Session, flush_context: UOWTransaction):
        # when sqlalchemy is flushing it is done in a sub-transaction,
        # not the root one. So when calling our 'commit' from here
        # we are not in our root transaction, so changes will not be
        # written to repository.
        self.commit(session)

    def rollback(self, session: Session) -> None:
        if not self.running:
            return

        transaction = self.get_transaction(session)
        if transaction is None:
            return

        transaction.rollback()


class SessionBlobStoreService(Service):
    """A blob store service that is session aware, i.e content is actually
    written or delete at commit time.

    All content is stored using the main :class:`BlobStoreService`.
    """

    name = "session_blob_store"
    AppStateClass = SessionBlobStoreState

    def __init__(self, *args, **kwargs) -> None:
        self.__listening = False
        super().__init__(*args, **kwargs)

    def init_app(self, app: Application) -> None:
        super().init_app(app)

        path = Path(app.instance_path, "tmp", "files_transactions")
        if not path.exists():
            path.mkdir(0o775, parents=True)

        with app.app_context():
            self.app_state.path = path.resolve()

        if not self.__listening:
            self.start_listening()

    def start_listening(self) -> None:
        self.__listening = True
        listen = sa.event.listen
        listen(Session, "after_transaction_create", self.create_transaction)
        listen(Session, "after_transaction_end", self.end_transaction)
        listen(Session, "after_begin", self.begin)
        listen(Session, "after_commit", self.commit)
        listen(Session, "after_flush", self.flush)
        listen(Session, "after_rollback", self.rollback)
        # appcontext_tearing_down.connect(self.clear_transaction, app)

    def _session_for(self, model_or_session: Model | Session) -> Session:
        """Return session instance for object parameter.

        - If parameter is a session instance, it is returned as is.

        - If parameter is a registered model instance, its session will be used.

        - If parameter is a detached model instance, or None, application scoped
          session will be used (db.session()).

        - If parameter is a scoped_session instance, a new session will be
          instaniated.
        """
        match model_or_session:
            case None:
                return db.session()

            case Session():
                return model_or_session

            case sa.orm.scoped_session():
                return model_or_session()

        session = sa.orm.object_session(model_or_session)

        if session is None:
            return db.session()

        return session

    # Blob store interface
    def get(
        self, session: Session | Blob, uuid: UUID, default: Path | None = None
    ) -> Path | None:
        # assert isinstance(session, Session)
        _assert_uuid(uuid)

        session = self._session_for(session)
        transaction = self.app_state.get_transaction(session)
        if transaction is None:
            return default
        try:
            val = transaction.get(uuid)
        except KeyError:
            return default

        if val is _NULL_MARK:
            val = blob_store.get(uuid, default)

        return val

    def set(
        self,
        session: Session | Blob,
        uuid: UUID,
        content: IO | bytes | str,
        encoding: str = "utf-8",
    ) -> None:
        _assert_uuid(uuid)
        session = self._session_for(session)
        transaction = self.app_state.get_transaction(session)
        if transaction is None:
            msg = "transaction is None in blob store service"
            raise RuntimeError(msg)
        transaction.set(uuid, content, encoding)

    def delete(self, session: Session | Blob, uuid: UUID) -> None:
        _assert_uuid(uuid)

        session = self._session_for(session)
        transaction = self.app_state.get_transaction(session)
        if self.get(session, uuid) is not None:
            transaction.delete(uuid)

    # session event handlers
    @Service.if_running
    def create_transaction(
        self, session: Session, _transaction: SessionTransaction
    ) -> None:
        self.app_state.create_transaction(session)

    @Service.if_running
    def end_transaction(
        self, session: Session, _transaction: SessionTransaction
    ) -> None:
        self.app_state.end_transaction(session)

    @Service.if_running
    def begin(
        self,
        session: Session,
        _transaction: SessionTransaction,
        _connection: Connection,
    ) -> None:
        self.app_state.begin(session)

    @Service.if_running
    def commit(self, session: Session) -> None:
        self.app_state.commit(session)

    @Service.if_running
    def flush(self, session: Session, _flush_context: UOWTransaction) -> None:
        self.app_state.flush(session)

    @Service.if_running
    def rollback(self, session: Session) -> None:
        self.app_state.rollback(session)


session_blob_store = SessionBlobStoreService()


class BlobStoreTransaction:
    """Temporary local storage of file content during a transaction on
    a Blob (and related child blobs).

    Transaction shall end by either a commit or a rollback.

    Intermediate blob storage lies in self.tmp_folder and is cleared
    at end of transaction.

    BlobStoreTransaction is used by SessionBlobStoreService and the
    commit() method triggers final storage through the local "blob_store"
    service.

    Use the set() method to add actual content to the transaction and get()
    to retrieve the path of the underlying content.
    """

    def __init__(
        self, root_path: Path, parent: BlobStoreTransaction | None = None
    ) -> None:
        self.tmp_folder = root_path / str(uuid1())
        # if parent is not None and parent.cleared:
        #   parent = None

        self._parent = parent
        self._deleted: set[UUID] = set()
        self._set: set[UUID] = set()
        self._cleared: bool = False

    @property
    def cleared(self) -> bool:
        return self._cleared

    def __del__(self) -> None:
        if not self._cleared:
            self._clear()

    def _clear(self) -> None:
        if self._cleared:
            return

        # make sure transaction is not usable anymore
        if self.tmp_folder.exists():
            shutil.rmtree(self.tmp_folder)

        del self.tmp_folder
        del self._deleted
        del self._set
        self._cleared = True

    def begin(self) -> None:
        if not self.tmp_folder.exists():
            self.tmp_folder.mkdir(0o700)

    def rollback(self) -> None:
        self._clear()

    def commit(self) -> None:
        """Merge modified objects into parent transaction.

        Once commited a transaction object is not usable anymore

        :param:session: current sqlalchemy Session
        """
        if self._cleared:
            return

        if self._parent:
            # nested transaction
            self._commit_parent()
        else:
            self._commit_blob_store()
        self._clear()

    def _commit_blob_store(self) -> None:
        if self._cleared:
            return
        assert self._parent is None

        for uuid in self._deleted:
            with contextlib.suppress(KeyError):
                blob_store.delete(uuid)

        for uuid in self._set:
            blob_store.set(uuid, self.uuid_path(uuid).read_bytes())

    def uuid_path(self, uuid: UUID) -> Path:
        return self.tmp_folder / str(uuid)

    def _commit_parent(self) -> None:
        parent = self._parent
        assert parent
        parent._deleted |= self._deleted
        parent._deleted -= self._set

        parent._set |= self._set
        parent._set -= self._deleted

        if self._set:
            parent.begin()  # ensure p.path exists

        for uuid in self._set:
            self.uuid_path(uuid).replace(parent.uuid_path(uuid))

    def _add_to(self, uuid: UUID, dest: set[UUID], other: set[UUID]) -> None:
        """Add `item` to `dest` set, ensuring `item` is not present in `other`
        set."""
        _assert_uuid(uuid)
        other.discard(uuid)
        dest.add(uuid)

    def delete(self, uuid: UUID) -> None:
        self._add_to(uuid, self._deleted, self._set)

    def set(
        self,
        uuid: UUID,
        content: IO | bytes | str,
        encoding: str | None = "utf-8",
    ) -> None:
        self.begin()
        self._add_to(uuid, self._set, self._deleted)

        if hasattr(content, "read"):
            content = content.read()

        if isinstance(content, bytes):
            mode = "wb"
            encoding = None
        else:
            mode = "wt"
        dest = self.uuid_path(uuid)
        with dest.open(mode, encoding=encoding) as file:
            file.write(content)

    def get(self, uuid: UUID) -> Any:
        if uuid in self._deleted:
            raise KeyError(uuid)

        if uuid in self._set:
            path = self.uuid_path(uuid)
            assert path.exists()
            return path

        if self._parent:
            return self._parent.get(uuid)

        return _NULL_MARK
