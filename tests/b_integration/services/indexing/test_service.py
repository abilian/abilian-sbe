# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import importlib
import threading
from typing import TYPE_CHECKING, cast

import sqlalchemy as sa
from pytest import MonkeyPatch, fixture
from whoosh.filedb.filestore import FileStorage
from whoosh.index import LockError

from abilian.core.entities import Entity
from abilian.services import get_service

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy.orm import Session

    from abilian.app import Application
    from abilian.services.indexing.service import WhooshIndexService


class IndexedContact(Entity):
    # default is 'test_service.IndexedContact'
    entity_type = "abilian.services.indexing.IndexedContact"
    name = sa.Column(sa.UnicodeText)


@fixture
def svc(app: Application) -> Iterator[WhooshIndexService]:
    _svc = cast("WhooshIndexService", get_service("indexing"))
    with app.app_context():
        _svc.start(ignore_state=True)
        yield _svc


def test_app_state(app: Application, svc: WhooshIndexService) -> None:
    state = svc.app_state
    assert IndexedContact in state.indexed_classes
    assert IndexedContact.entity_type in svc.adapted
    assert IndexedContact.entity_type in state.indexed_fqcn


def test_index_only_after_final_commit(
    app: Application, session: Session, svc: WhooshIndexService
) -> None:
    contact = IndexedContact(name="John Doe")

    state = svc.app_state

    savepoint = session.begin(nested=True)
    assert state.to_update == []

    session.add(contact)
    # no commit: model is in wait queue
    session.flush()
    assert state.to_update == [("new", contact)]

    # commit but in a sub transaction: model still in wait queue
    savepoint.commit()
    assert state.to_update == [("new", contact)]

    # 'final' commit: models sent for indexing update
    session.commit()
    assert state.to_update == []


def test_clear(app: Application, svc: WhooshIndexService) -> None:
    # just check no exception happens
    svc.clear()

    # check no double stop (would raise AssertionError from service base)
    svc.start()
    svc.stop()
    svc.clear()


def test_reindex_rebuilds_the_index_from_the_database(
    app: Application, session: Session, svc: WhooshIndexService
) -> None:
    """`flask reindex`, which a migrated site runs: the index is not copied."""
    from abilian.cli.indexing import reindex

    contact = IndexedContact(name="Ada Lovelace")
    session.add(contact)
    session.commit()
    # `clear` empties the index and stops the service, which starts again empty.
    svc.clear()
    svc.start(ignore_state=True)
    index = svc.app_state.indexes["default"]
    assert index.doc_count() == 0

    result = app.test_cli_runner().invoke(reindex)

    assert result.exit_code == 0, result.output
    with index.searcher() as searcher:
        indexed = [f["object_key"] for f in searcher.all_stored_fields()]
    assert indexed == [contact.object_key]


def test_index_update_fails_when_the_index_stays_locked(
    app: Application,
    svc: WhooshIndexService,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A locked index raised nothing: the update waited in a thread forever,
    where Dramatiq could not see it fail and retry."""
    # The package exports the service instance under the module's name.
    indexing = importlib.import_module("abilian.services.indexing.service")
    monkeypatch.setattr(indexing, "INDEX_WRITER_TIMEOUT", 0.2)
    # On disk, as in production: the RAM index's thread lock ignores timeouts.
    indexes = svc.app_state.indexes
    schema = indexes["default"].schema
    monkeypatch.setitem(
        indexes, "default", FileStorage(str(tmp_path)).create_index(schema)
    )
    outcome: list[BaseException | None] = []

    def update() -> None:
        with app.app_context():
            try:
                indexing.index_update(index="default", items=[])
            except LockError as e:
                outcome.append(e)
            else:
                outcome.append(None)

    blocker = svc.app_state.indexes["default"].writer()
    try:
        thread = threading.Thread(target=update, daemon=True)
        thread.start()
        thread.join(timeout=5)
    finally:
        blocker.cancel()

    assert len(outcome) == 1
    assert isinstance(outcome[0], LockError)
