# coding=utf-8
"""
"""
from __future__ import absolute_import

from datetime import datetime, timedelta

import mock
from pytz import UTC

from abilian.core.models.subjects import User
from abilian.sbe.apps.documents import lock
from abilian.sbe.apps.documents.lock import Lock
from abilian.testing import BaseTestCase


def test_lock():
    date = datetime(2015, 10, 22, 14, 58, 42, tzinfo=UTC)
    l = Lock(user_id=3, user=u'Joe Smith', date=date)

    d = l.as_dict()
    assert d == dict(user_id=3,
                     user=u'Joe Smith',
                     date=u'2015-10-22T14:58:42+00:00')
    l = Lock.from_dict(d)
    assert l.user_id == 3
    assert l.user == u'Joe Smith'
    assert l.date == date


class LockTestCase(BaseTestCase):

    SERVICES = ('security',)

    def test_lock(self):
        session = self.app.db.session()
        user = User(email=u'test@example.com',
                    first_name=u'Joe',
                    last_name=u'Smith',
                    can_login=True)
        other = User(email=u'other@exemple.com')
        session.add(user)
        session.add(other)
        session.commit()

        # set 30s lifetime
        self.app.config['SBE_LOCK_LIFETIME'] = 30
        dt_patcher = mock.patch.object(
            lock, 'utcnow', mock.Mock(wraps=lock.utcnow))
        with dt_patcher as mocked:
            created_at = datetime(2015, 10, 22, 14, 58, 42, tzinfo=UTC)
            mocked.return_value = created_at

            self.login(user)
            l = Lock.new()
            assert l.user_id == user.id
            assert l.user == u'Joe Smith'
            assert l.date == created_at
            assert l.is_owner()
            assert l.is_owner(user)
            assert not l.is_owner(other)

            assert l.lifetime == 30
            mocked.return_value = created_at + timedelta(seconds=40)
            assert l.expired

            mocked.return_value = created_at + timedelta(seconds=20)
            assert not l.expired

            self.login(other)
            assert not l.is_owner()
