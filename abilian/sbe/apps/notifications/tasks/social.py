# coding=utf-8
"""
"""
from __future__ import absolute_import

from datetime import timedelta, datetime
from sqlalchemy import and_, or_
from validate_email import validate_email

from celery.task import periodic_task
from celery.schedules import crontab

from flask import current_app as app
from flask.ext.mail import Message
from flask.ext.security.utils import md5

from abilian.i18n import render_template_i18n
from abilian.core.models.subjects import User
from abilian.services.activity import ActivityEntry
from abilian.services.auth.views import get_serializer

from abilian.sbe.apps.documents.models import Document
from abilian.sbe.apps.documents.repository import repository
from abilian.sbe.apps.forum.models import Thread, Post
from abilian.sbe.apps.wiki.models import WikiPage

from .. import TOKEN_SERIALIZER_NAME


@periodic_task(run_every=crontab(hour=8, minute=0, ), ignore_result=True)
def send_daily_social_digest_task():
  # a request_context is required when rendering templates
  with app.test_request_context('/send_daily_social_updates'):
    send_daily_social_digest()


def send_daily_social_digest():
  for user in User.query.filter(User.can_login == True).all():
    preferences = app.services['preferences']
    prefs = preferences.get_preferences(user)

    if not prefs.get('sbe:notifications:daily', False):
      continue

    # Defensive programming.
    if not validate_email(user.email):
      continue

    try:
      send_daily_social_digest_to(user)
    except:
      app.logger.error('Error sending daily social digest', exc_info=True)


def send_daily_social_digest_to(user):
  """Send to a given user a daily digest of activities in its communities.

  Return 1 if mail sent, 0 otherwise.
  """
  mail = app.extensions['mail']
  config = app.config
  sbe_config = config['ABILIAN_SBE']
  sender = config.get('BULK_MAIL_SENDER', config['MAIL_SENDER'])

  recipient = user.email
  subject = sbe_config['DAILY_SOCIAL_DIGEST_SUBJECT']

  digests = []

  happened_after = datetime.utcnow() - timedelta(days=1)
  for membership in user.communautes_membership:
    community = membership.community
    if not community:
      # TODO: should not happen but it does. Fix root cause instead.
      continue
    digest = CommunityDigest(community)
    AE = ActivityEntry
    activities = AE.query.filter(
        and_(AE.happened_at > happened_after,
             or_(and_(AE.target_type == community.object_type,
                      AE.target_id == community.id),
                 and_(AE.object_type == community.object_type,
                      AE.object_id == community.id),))
        ).all()
    for activity in activities:
      digest.update_from_activity(activity, user)
    if not digest.is_empty():
      digests.append(digest)

  if not digests:
    return 0

  token = generate_unsubscribe_token(user)
  msg = Message(subject, sender=sender, recipients=[recipient])
  msg.body = render_template_i18n("notifications/daily-social-digest.txt",
                             digests=digests, token=token)
  msg.html = render_template_i18n("notifications/daily-social-digest.html",
                             digests=digests, token=token)

  mail.send(msg)
  return 1


def generate_unsubscribe_token(user):
  """Generates a unique unsubscription token for the specified user.

  :param user: The user to work with
  """
  data = [str(user.id), md5(user.password)]
  return get_serializer(TOKEN_SERIALIZER_NAME).dumps(data)


class CommunityDigest(object):
  def __init__(self, community):
    self.community = community

    self.new_members = []
    self.new_documents = []
    self.updated_documents = []
    self.new_conversations = []
    self.updated_conversations = []
    self.new_wiki_pages = []
    self.updated_wiki_pages = []

  def is_empty(self):
    return (not self.new_members and not self.new_documents
            and not self.updated_documents and not self.new_conversations
            and not self.updated_conversations and not self.new_wiki_pages
            and not self.updated_wiki_pages)

  def update_from_activity(self, activity, user):
    actor = activity.actor
    obj = activity.object

    # TODO ?
    #target = activity.target

    if activity.verb == 'join':
      self.new_members.append(actor)

    elif activity.verb == 'post':
      if isinstance(obj, Document) and repository.has_access(user, obj):
        self.new_documents.append(obj)
      elif isinstance(obj, WikiPage):
        self.new_wiki_pages.append(obj)
      elif isinstance(obj, Thread):
        self.new_conversations.append(obj)
      elif isinstance(obj, Post):
        self.updated_conversations.append(obj.thread)

    elif activity.verb == 'update':
      if isinstance(obj, Document) and repository.has_access(user, obj):
        if obj in self.new_documents:
          return
        self.updated_documents.append(obj)
      elif isinstance(obj, WikiPage):
        if obj in self.new_wiki_pages:
          return
        self.updated_wiki_pages.append(obj)
