# Copyright (c) 2012-2024, Abilian SAS

"""`flask reindex` rebuilds the index, and says when it could not."""

from __future__ import annotations

import contextlib
import threading
from typing import TYPE_CHECKING

import sqlalchemy as sa
from pytest import fixture
from whoosh.fields import TEXT, Schema
from whoosh.filedb.filestore import FileStorage

from abilian.cli.indexing import STOP, reindex, single_transaction
from abilian.core.entities import Entity
from abilian.services import get_service

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.services.indexing.service import WhooshIndexService


class ReindexedNote(Entity):
    entity_type = "tests.cli.ReindexedNote"
    name = sa.Column(sa.UnicodeText)


@fixture
def index(app: Application, db: SQLAlchemy) -> Iterator[WhooshIndexService]:
    service = get_service("indexing")
    service.start(ignore_state=True)
    yield service
    service.stop()


def indexed_names(index: WhooshIndexService) -> set[str]:
    with index.index().searcher() as searcher:
        return {doc.get("name") for doc in searcher.documents()}


def test_clear_rebuilds_the_index_from_the_database(
    app: Application, db: SQLAlchemy, index: WhooshIndexService
) -> None:
    db.session.add(ReindexedNote(name="kept"))
    db.session.commit()

    result = app.test_cli_runner().invoke(reindex, ["--clear"])

    assert result.exit_code == 0, result.output
    assert "kept" in indexed_names(index)


def test_a_class_that_cannot_be_read_fails_the_command(
    app: Application, db: SQLAlchemy, index: WhooshIndexService
) -> None:
    db.session.commit()
    ReindexedNote.__table__.drop(db.engine)

    result = app.test_cli_runner().invoke(reindex)

    assert result.exit_code == 1
    assert "ReindexedNote" in result.output


def test_clearing_waits_for_the_index_the_worker_is_writing(tmp_path: Path) -> None:
    index = FileStorage(str(tmp_path)).create_index(Schema(name=TEXT(stored=True)))
    with index.writer() as writer:
        writer.add_document(name="stale")
    # As the worker does, indexing a change when the command starts.
    busy = index.writer()
    threading.Timer(0.5, busy.cancel).start()

    strategy = single_transaction(index, clear=True)
    next(strategy)
    with contextlib.suppress(StopIteration):
        strategy.send(STOP)

    assert index.doc_count() == 0
