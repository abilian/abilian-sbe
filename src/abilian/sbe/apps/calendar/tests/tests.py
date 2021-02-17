from datetime import datetime

from flask import url_for
from pytest import mark

from abilian.sbe.apps.calendar.models import Event


def test_create_event() -> None:
    start = datetime.now()
    event = Event(name="Test thread", start=start)
    assert event  # TODO


@mark.skip
def test(community1, client, req_ctx):
    response = client.get(url_for("calendar.index", community_id=community1.slug))
    assert response.status_code == 200


# @mark.skip
# def test_event_indexed(community1, community2, db, client, req_ctx):
#     start = datetime.now()
#     event1 = Event(name="Test event", community=community1, start=start)
#     event2 = Event(name="Test other event", community=community2, start=start)
#     db.session.add(event1)
#     db.session.add(event2)
#     db.session.commit()
#
#     svc = self.svc
#     obj_types = (Event.entity_type,)
#     with self.login(self.user_no_community):
#         res = svc.search("event", object_types=obj_types)
#         assert len(res) == 0
#
#     with self.login(self.user):
#         res = svc.search("event", object_types=obj_types)
#         assert len(res) == 1
#         hit = res[0]
#         assert hit["object_key"] == event1.object_key
#
#     with self.login(self.user_c2):
#         res = svc.search("event", object_types=obj_types)
#         assert len(res) == 1
#         hit = res[0]
#         assert hit["object_key"] == event2.object_key
