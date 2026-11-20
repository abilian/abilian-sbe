# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from pytest import fixture

from abilian.core.entities import Entity
from abilian.core.models.subjects import User
from abilian.services.activity.service import ActivityService


class Message1(Entity):
    pass


@fixture
def activity_service(app, db):
    service = ActivityService()
    service.start()
    yield service
    service.stop()


def test(app, session, activity_service) -> None:
    service = activity_service
    user = User(email="test@example.com")
    message = Message1(creator=user, owner=user, name="test message")

    with session.begin_nested():
        session.add(user)
        session.add(message)
    service.log_activity(None, user, "post", message)
    session.flush()

    m_id, m_type = message.id, message.entity_type

    entries = service.entries_for_actor(user, 10)
    assert len(entries) == 1

    entry = entries[0]
    assert entry.actor == user
    assert entry.actor_id == user.id
    assert entry.object == message
    assert entry.object_type == m_type
    assert entry._fk_object_id == m_id
    assert entry.object_id == m_id
    assert entry.target is None

    # test entry doesn't reference target if its in deleted state
    session.delete(message)
    session.flush()
    # send activity after flush: activity should not reference
    # an instance in "deleted state"
    service.log_activity(None, user, "delete", message)
    session.flush()

    entries = service.entries_for_actor(user, 10)
    assert len(entries) == 2

    entry = entries[1]
    assert entry.object is None
    assert entry.object_type == m_type
    assert entry._fk_object_id is None
    assert entry.object_id == m_id
    assert entry.target is None
