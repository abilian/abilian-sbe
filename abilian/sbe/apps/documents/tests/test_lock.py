# coding=utf-8
"""
"""
from __future__ import absolute_import, print_function, unicode_literals

from datetime import datetime, timedelta

import mock
from pytz import UTC

from abilian.core.models.subjects import User
from abilian.sbe.apps.documents import lock
from abilian.sbe.apps.documents.lock import Lock
from abilian.testing import BaseTestCase


def test_lock():
    date = datetime(2015, 10, 22, 14, 58, 42, tzinfo=UTC)
    l = Lock(user_id=3, user='Joe Smith', date=date)

    d = l.as_dict()
    assert d == dict(
        user_id=3, user='Joe Smith', date='2015-10-22T14:58:42+00:00')
    l = Lock.from_dict(d)
    assert l.user_id == 3
    assert l.user == 'Joe Smith'
    assert l.date == date


class LockTestCase(BaseTestCase):

    SERVICES = ('security',)

    def test_lock(self):
        session = self.app.db.session()
        user = User(
            email='test@example.com',
            first_name='Joe',
            last_name='Smith',
            can_login=True)
        other = User(email='other@exemple.com')
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
            assert l.user == 'Joe Smith'
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
