# coding=utf-8

from unittest import TestCase
from nose.tools import ok_

from abilian.core.entities import all_entity_classes
from abilian.core.models.subjects import User, Group

from ..models import Message, PrivateMessage


class TestModels(TestCase):

  def check_editable(self, object):
    if hasattr(object, '__editable__'):
      for k in object.__editable__:
        self.assert_(hasattr(object, k))


class TestUsers(TestModels):

  def test_user(self):
    user = User(first_name=u"John", last_name=u"Test User", email=u"test@example.com", password="toto")
    self.check_editable(user)

    self.assertEquals(u"John Test User", user.name)
    self.assertEquals(u"John Test User", unicode(user))
    #self.assertEquals(len(user.messages), 0)

  def test_user_follow(self):
    # id is provided by DB (which is not used in this test), and is required for
    # having in (user1 != user2) == True
    user1 = User(id=1, first_name=u"John", last_name=u"Test User 1", email=u"test1@example.com", password="toto")
    user2 = User(id=2, first_name=u"Joe", last_name=u"Test User 2", email=u"test2@example.com", password="toto")

    self.assertEquals(0, len(user1.followers))
    self.assertEquals(0, len(user1.followees))
    self.assertEquals(0, len(user2.followers))
    self.assertEquals(0, len(user2.followees))

    user1.follow(user2)

    self.assert_(user1.is_following(user2))
    self.assertEquals(1, len(user2.followers))
    self.assertEquals(1, len(user1.followees))
    self.assertEquals(0, len(user2.followees))
    self.assertEquals(0, len(user1.followers))
    self.assert_(user2 in user1.followees)

    user1.unfollow(user2)

    self.assert_(not user1.is_following(user2))
    self.assertEquals(0, len(user1.followers))
    self.assertEquals(0, len(user1.followees))
    self.assertEquals(0, len(user2.followers))
    self.assertEquals(0, len(user2.followees))
    self.assert_(user2 not in user1.followers)

  def test_group(self):
    user = User(first_name=u"John", last_name=u"Test User", email=u"test@example.com", password="toto")
    group = Group(name=u"Group 1")

    user.join(group)

    self.assert_(user.is_member_of(group))
    self.assertEquals(1, len(group.members))
    self.assertEquals(1, len(user.groups))
    self.assertEqual([user], group.members)
    self.assertEqual([group], user.groups)

    user.leave(group)

    self.assert_(not user.is_member_of(group))
    self.assertEquals(0, len(group.members))
    self.assertEquals(0, len(user.groups))


class TestContent(TestModels):

  def test_private_message(self):
    pm = PrivateMessage(creator_id=0, recipient_id=0)
    self.check_editable(pm)

  def test_status_update(self):
    user = User(first_name=u"John", last_name=u"Test User", email=u"test@example.com", password="toto")
    #self.assertEquals(len(user.messages), 0)

    message = Message()
    message.author = user
    self.check_editable(message)

    #self.assertEquals(len(user.messages), 1)
    #self.assertEquals(user.messages[0], message)
    #self.assertEquals(message.author_id, user.uid)

  def test_tags(self):
    m = Message(content=u"abc #123 #cde #voilà_l_été #789")
    self.assertEquals([u'123', u'cde', u'voilà_l_été', u'789'], m.tags)

  def test_get_all_entity_classes(self):
    classes = all_entity_classes()
    ok_(Message in classes)
    ok_(PrivateMessage in classes)
