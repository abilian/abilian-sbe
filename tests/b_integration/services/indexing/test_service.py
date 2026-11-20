# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import sqlalchemy as sa
from pytest import fixture

from abilian.core.entities import Entity
from abilian.services import get_service

if TYPE_CHECKING:
    from collections.abc import Iterator

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
