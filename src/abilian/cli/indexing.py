# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import contextlib
import time
from collections import deque
from typing import TYPE_CHECKING

import click
import sqlalchemy as sa
import whoosh
import whoosh.index
from flask.cli import with_appcontext
from flask_super.cli import command
from loguru import logger
from sqlalchemy.orm.session import Session
from tqdm import tqdm
from whoosh.writing import CLEAR, AsyncWriter

from abilian.core.extensions import db
from abilian.services import get_service

if TYPE_CHECKING:
    from abilian.core.entities import Entity

STOP = object()
COMMIT = object()


@command()
@click.option("--batch-size", default=0)
@click.option("--progressive/--no-progressive")
@click.option("--clear/--no-clear")
@with_appcontext
def reindex(clear: bool, progressive: bool, batch_size: int) -> None:
    """Reindex all content; optionally clear index before.

    All is done in asingle transaction by default.

    :param clear: clear index content.
    :param progressive: don't run in a single transaction.
    :param batch_size: number of documents to process before writing to the
                     index. Unused in single transaction mode. If `None` then
                     all documents of same content type are written at once.
    """
    reindexer = Reindexer(clear, progressive, batch_size)
    reindexer.reindex_all()


class Reindexer:
    def __init__(self, clear: bool, progressive: bool, batch_size: int) -> None:
        self.clear = clear
        self.progressive = progressive
        self.batch_size = int(batch_size or 0)

        self.index_service = get_service("indexing")
        self.index = self.index_service.app_state.indexes["default"]
        self.adapted = self.index_service.adapted
        # Its own session, apart from the app's: each class is read in a
        # transaction of its own (`reindex_class`).
        self.session = Session(bind=db.engine)
        self.indexed: set[str] = set()
        self.cleared: set[str] = set()

        strategy = progressive_mode if self.progressive else single_transaction
        self.strategy = strategy(self.index, clear=self.clear)

    def reindex_all(self) -> None:
        next(self.strategy)  # starts generator

        indexed_classes = self.index_service.app_state.indexed_classes
        for cls in sorted(indexed_classes, key=lambda c: c.__name__):
            self.reindex_class(cls)

        with contextlib.suppress(StopIteration):
            self.strategy.send(STOP)

        with contextlib.suppress(StopIteration):
            self.strategy.close()

    def reindex_class(self, cls: Entity) -> None:
        current_object_type = cls._object_type()

        if not self.clear and current_object_type not in self.cleared:
            self.strategy.send(current_object_type)
            self.cleared.add(current_object_type)

        adapter = self.adapted.get(current_object_type)

        if not adapter or not adapter.indexable:
            return

        name = cls.__name__

        with self.session.begin():
            query = self.session.query(cls).options(sa.orm.lazyload("*"))
            try:
                count = query.count()
            except Exception as e:
                logger.exception(
                    "Indexing error on class {name}: {exc}",
                    name=name,
                    exc=repr(e),
                )
                return

            print("*" * 79)
            print(f"{name}")
            if count == 0:
                print("*" * 79)
                print(f"{name}")
                return

            print("*" * 79)
            print(f"{name}")

            with tqdm(total=count) as bar:
                self.reindex_batch(query, current_object_type, adapter, bar)

            if not self.batch_size:
                self.strategy.send(COMMIT)

        self.strategy.send(COMMIT)

    def reindex_batch(self, query, current_object_type, adapter, bar) -> None:
        count = 0
        for obj in query.yield_per(1000):
            count += 1
            if obj.object_type != current_object_type:
                # may happen if obj is a subclass and its parent class
                # is also indexable
                bar.update()
                continue

            object_key = obj.object_key

            if object_key in self.indexed:
                bar.update()
                continue

            document = self.index_service.get_document(obj, adapter)
            self.strategy.send(document)
            self.indexed.add(object_key)

            if self.batch_size and (count % self.batch_size) == 0:
                bar.update()
                self.strategy.send(COMMIT)

            bar.update()


# indexing strategies
def single_transaction(index, clear):
    with AsyncWriter(index) as writer:
        if clear:
            print("*" * 80)
            print("WILL CLEAR INDEX BEFORE REINDEXING")
            print("*" * 80)
            writer.writer.mergetype = CLEAR

        doc = yield True
        while doc is not STOP:
            if doc is COMMIT:
                doc = yield True
                continue
            if isinstance(doc, str):
                writer.delete_by_term("object_type", doc)
            else:
                writer.add_document(**doc)
            doc = yield True

        print("Writing Index...", end=" ")

    print("Done.")


def progressive_mode(index, clear):
    if clear:
        writer = _get_writer(index)
        print("*" * 80)
        print("CLEAR INDEX BEFORE REINDEXING")
        print("*" * 80)
        writer.mergetype = CLEAR
        writer.commit()
        del writer

    queue = deque()
    doc = yield True
    while doc is not STOP:
        if doc is COMMIT:
            writer = _get_writer(index)
            while queue:
                doc = queue.pop()
                if isinstance(doc, str):
                    writer.delete_by_term("object_type", doc)
                else:
                    writer.add_document(**doc)
            writer.commit()
            del writer
        else:
            queue.append(doc)

        doc = yield True


def _get_writer(index):
    writer = None
    while writer is None:
        try:
            writer = index.writer()
        except whoosh.index.LockError:
            time.sleep(0.25)

    return writer
