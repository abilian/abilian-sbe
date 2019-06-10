# coding=utf-8
""""""
from datetime import datetime, timedelta
from unittest import mock

from abilian.core.models.subjects import User
from flask.ctx import RequestContext
from flask_login import login_user
from pytz import UTC
from sqlalchemy.orm import Session

from abilian.sbe.app import Application
from abilian.sbe.apps.documents import lock
from abilian.sbe.apps.documents.lock import Lock


def test_lock() -> None:
    date = datetime(2015, 10, 22, 14, 58, 42, tzinfo=UTC)
    l = Lock(user_id=3, user="Joe Smith", date=date)
    d = l.as_dict()
    assert d == {"user_id": 3, "user": "Joe Smith", "date": "2015-10-22T14:58:42+00:00"}

    l = Lock.from_dict(d)
    assert l.user_id == 3
    assert l.user == "Joe Smith"
    assert l.date == date


def test_lock2(app: Application, session: Session, req_ctx: RequestContext) -> None:
    user = User(
        email="test@example.com", first_name="Joe", last_name="Smith", can_login=True
    )
    other = User(email="other@exemple.com")
    session.add(user)
    session.add(other)
    session.commit()

    # set 30s lifetime
    app.config["SBE_LOCK_LIFETIME"] = 30
    dt_patcher = mock.patch.object(lock, "utcnow", mock.Mock(wraps=lock.utcnow))
    with dt_patcher as mocked:
        created_at = datetime(2015, 10, 22, 14, 58, 42, tzinfo=UTC)
        mocked.return_value = created_at

        login_user(user)
        l = Lock.new()
        assert l.user_id == user.id
        assert l.user == "Joe Smith"
        assert l.date == created_at
        assert l.is_owner()
        assert l.is_owner(user)
        assert not l.is_owner(other)

        assert l.lifetime == 30
        mocked.return_value = created_at + timedelta(seconds=40)
        assert l.expired

        mocked.return_value = created_at + timedelta(seconds=20)
        assert not l.expired

        login_user(other)
        assert not l.is_owner()
