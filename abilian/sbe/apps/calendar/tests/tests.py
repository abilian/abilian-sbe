# coding=utf-8
""""""
from __future__ import absolute_import, print_function, unicode_literals

from datetime import datetime

from flask import url_for
from pytest import mark

from abilian.sbe.apps.communities.tests.base import CommunityBaseTestCase, \
    CommunityIndexingTestCase

from ..models import Event


def test_create_event():
    start = datetime.now()
    event = Event(name="Test thread", start=start)
    assert event  # TODO


class IndexingTestCase(CommunityIndexingTestCase):
    @mark.skip
    def test_event_indexed(self):
        start = datetime.now()
        event1 = Event(name="Test event", community=self.community, start=start)
        event2 = Event(name="Test other event", community=self.c2, start=start)
        self.session.add(event1)
        self.session.add(event2)
        self.session.commit()

        svc = self.svc
        obj_types = (Event.entity_type,)
        with self.login(self.user_no_community):
            res = svc.search("event", object_types=obj_types)
            assert len(res) == 0

        with self.login(self.user):
            res = svc.search("event", object_types=obj_types)
            assert len(res) == 1
            hit = res[0]
            assert hit["object_key"] == event1.object_key

        with self.login(self.user_c2):
            res = svc.search("event", object_types=obj_types)
            assert len(res) == 1
            hit = res[0]
            assert hit["object_key"] == event2.object_key


class NoLoginViewTest(CommunityBaseTestCase):
    """Test correct url response, without login or security involved."""

    @mark.skip
    def test(self):
        response = self.client.get(
            url_for("calendar.index", community_id=self.community.slug)
        )
        assert response.status_code == 200
