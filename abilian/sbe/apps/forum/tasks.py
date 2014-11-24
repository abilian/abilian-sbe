# coding=utf-8
"""
Celery tasks related to document transformation and preview.
"""
from __future__ import absolute_import

import logging

from flask import render_template, current_app
from flask.ext.mail import Message
from abilian.core.extensions import celery, mail


logger = logging.getLogger(__package__)


@celery.task(ignore_result=True)
def send_post_by_email(post_id):
  """Send a post to community members by email.
  """
  from .models import Post

  with current_app.test_request_context('/send_post_by_email'):
    post = Post.query.get(post_id)
    if post is None:
      # deleted after task queued, but before task run
      return

    thread = post.thread
    community = thread.community

    logger.info("Sending new post by email to members of community %s"
                 % community.name)
    for member in community.members:
      if not member.can_login:
        continue
      send_post_to_user(community, post, member)


def send_post_to_user(community, post, member):
  recipient = member.email
  subject = u'[%s] %s' % (community.name, post.title)
  config = current_app.config
  sender = config.get('BULK_MAIL_SENDER', config['MAIL_SENDER'])
  msg = Message(subject, sender=sender, recipients=[recipient])
  msg.body = render_template("forum/mail/new_message.txt",
                             community=community, post=post, member=member)
  msg.html = render_template("forum/mail/new_message.html",
                             community=community, post=post, member=member)

  logger.debug("Sending new post by email to %s" % member.email)
  try:
    mail.send(msg)
  except:
    logger.error("Send mail to user failed",
                 exc_info=True) # log to sentry if enabled
