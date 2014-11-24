# coding=utf-8
"""
"""
from __future__ import absolute_import

from unittest import TestCase
from datetime import datetime, timedelta

from flask import url_for
from abilian.sbe.apps.communities.tests.base import (
  CommunityBaseTestCase, CommunityIndexingTestCase,
)

from .models import Thread, Post


class Test(TestCase):
  def test(self):
    thread = Thread(title="Test thread")
    post = thread.create_post()
    assert post in thread.posts
    self.assertEquals(post.name, u'Test thread')
    thread.title = u'new title'
    self.assertEquals(thread.name, u'new title')
    self.assertEquals(post.name, u'new title')

  def test_change_thread_copy_name(self):
    thread = Thread(title=u'thread 1')
    thread2 = Thread(title=u'thread 2')
    post = Post(thread=thread, body_html=u'post content')
    self.assertEquals(post.name, thread.name)
    post.thread = thread2
    self.assertEquals(post.name, thread2.name)


class IndexingTestCase(CommunityIndexingTestCase):

  def test_thread_indexed(self):
    thread = Thread(title=u'Community 1', community=self.community)
    self.session.add(thread)
    thread_other = Thread(title=u'Community 2: other', community=self.c2)
    self.session.add(thread_other)
    self.session.commit()

    svc = self.svc
    obj_types = (Thread.entity_type,)
    with self.login(self.user_no_community):
      res = svc.search(u'community', object_types=obj_types)
      self.assertEquals(len(res), 0)

    with self.login(self.user):
      res = svc.search(u'community', object_types=obj_types)
      self.assertEquals(len(res), 1)
      hit = res[0]
      self.assertEquals(hit['object_key'], thread.object_key)

    with self.login(self.user_c2):
      res = svc.search(u'community', object_types=obj_types)
      self.assertEquals(len(res), 1)
      hit = res[0]
      self.assertEquals(hit['object_key'], thread_other.object_key)


class ViewTestCase(CommunityBaseTestCase):
  def test(self):
    response = self.client.get(
      url_for("forum.index", community_id=self.community.slug))
    self.assert200(response)


  def test_posts_ordering(self):
    thread = Thread(community=self.community, title=u'test ordering')
    self.session.add(thread)
    t1 = datetime(2014, 06, 20, 15, 00, 00)
    p1 = Post(thread=thread, body_html=u'post 1', created_at=t1)
    t2 = datetime(2014, 06, 20, 15, 01, 00)
    p2 = Post(thread=thread, body_html=u'post 2', created_at=t2)
    self.session.flush()
    p1_id, p2_id = p1.id, p2.id

    self.assertEquals([p.id for p in thread.posts],
                      [p1_id, p2_id])

    # set post1 created after post2
    t1 = t1 + timedelta(minutes=2)
    p1.created_at = t1
    self.session.flush()
    self.session.expire(thread) # force thread.posts refreshed from DB
    self.assertEquals([p.id for p in thread.posts],
                      [p2_id, p1_id])
