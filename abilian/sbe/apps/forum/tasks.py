# coding=utf-8
"""
Celery tasks related to document transformation and preview.
"""
from __future__ import absolute_import

import mailbox
from os.path import expanduser

import bleach
import chardet
from pathlib import Path
from itsdangerous import URLSafeSerializer
from flask import current_app, g
from flask.ext.mail import Message
from flask.ext.babel import get_locale
from celery.task import periodic_task
from celery.utils.log import get_task_logger
from celery.schedules import crontab
from abilian.core.extensions import celery, mail, db
from abilian.core.models.subjects import User
from abilian.i18n import _l, render_template_i18n

from .forms import ALLOWED_ATTRIBUTES, ALLOWED_TAGS
from .models import Thread


MAIL_REPLY_MARKER = _l(u'_____Write above this line to post_____')

# logger = logging.getLogger(__package__)
# Celery logger
logger = get_task_logger(__name__)


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


def build_reply_email_address(name, post, member, domain):
  """
    Builds a reply-to email address
    embedding the locale, thread_id and user.id

  :param name: (str)    first part of an email address
  :param post: Post()   to get post.thread_id
  :param member: User() to get user.id
  :param domain: (str)  the last domain name of the email address
  :return: (unicode)    reply address for forum in the form
    test+IjEvMy8yLzQi.xjE04-4S0IzsdicTHKTAqcqa1fE@testcase.app.tld

    the hidden parameters are:  locale/post.thread_id/user.id
  """
  tag = current_app.config['MAIL_ADDRESS_TAG_CHAR']
  key = current_app.config['SECRET_KEY']
  locale = get_locale()
  serializer = URLSafeSerializer(key)
  uid = u'/'.join([str(locale), str(post.thread_id), str(member.id)])
  return name + tag + serializer.dumps(uid.decode('utf-8')) + u'@' + domain


def extract_email_destination(address):
  """
    Returns the values encoded in the email address.
  :param address: similar to test+IjEvMy8yLzQi.xjE04-4S0IzsdicTHKTAqcqa1fE@testcase.app.tld
  :return: List() of splitted values
  """
  name = address.rsplit('@', 1)[0]
  tag = current_app.config['MAIL_ADDRESS_TAG_CHAR']
  key = current_app.config['SECRET_KEY']
  serializer = URLSafeSerializer(key)
  values = name.rsplit(tag, 1)[1]
  return serializer.loads(values).split('/')


def has_subtag(address):
  """
    Returns True if a subtag (defined in the config.py as 'MAIL_ADDRESS_TAG_CHAR')
    was found in the name part of the address
    :param address: email adress
    :return: Boolean
  """
  name = address.rsplit('@', 1)[0]
  tag = current_app.config['MAIL_ADDRESS_TAG_CHAR']
  return (tag in name)


def send_post_to_user(community, post, member):
  recipient = member.email
  subject = u'[%s] %s' % (community.name, post.title)
  config = current_app.config
  sender = config.get('BULK_MAIL_SENDER', config['MAIL_SENDER'])
  SBE_FORUM_REPLY_BY_MAIL = config.get('SBE_FORUM_REPLY_BY_MAIL', False)
  if SBE_FORUM_REPLY_BY_MAIL and config['MAIL_ADDRESS_TAG_CHAR'] is not None:
    name = sender.rsplit('@', 1)[0]
    domain = sender.rsplit('@', 1)[1]
    replyto = build_reply_email_address(name, post, member, domain)
    msg = Message(subject, sender=sender, recipients=[recipient],
                  reply_to=replyto)
  else:
      msg = Message(subject, sender=sender, recipients=[recipient])
  msg.body = render_template_i18n(
      "forum/mail/new_message.txt",
      community=community, post=post, member=member,
      MAIL_REPLY_MARKER=MAIL_REPLY_MARKER,
      SBE_FORUM_REPLY_BY_MAIL=SBE_FORUM_REPLY_BY_MAIL,)
  msg.html = render_template_i18n(
      "forum/mail/new_message.html",
      community=community, post=post, member=member,
      MAIL_REPLY_MARKER=MAIL_REPLY_MARKER,
      SBE_FORUM_REPLY_BY_MAIL=SBE_FORUM_REPLY_BY_MAIL,)

  logger.debug("Sending new post by email to %s" % member.email)
  try:
    mail.send(msg)
  except:
    logger.error("Send mail to user failed",
                 exc_info=True)  # log to sentry if enabled


def extract_content(payload, marker):
  """Search the payload for marker, return content up to marker."""
  index = payload.rfind(marker)
  content = payload[:index]
  return content


def validate_html(payload):
  return bleach.clean(payload, tags=ALLOWED_TAGS,
                              attributes=ALLOWED_ATTRIBUTES, strip=True).strip()


def add_paragraph(newpost):
  """
    Adds surrounding <p>newpost</p> if necessary
  """
  newpost = newpost.strip()
  if not newpost.startswith(u'<p>'):
    newpost = u'<p>' + newpost + u'</p>'
  return newpost


def process(message, marker):
  """
    Check the message for marker presence and return the text up to it if present
    :raises LookupError otherwise.
    :param message: email.Message()
    :param marker: unicode
    :return: sanitized html upto marker from message
  """
  content = {}
  newpost = ''
  # Iterate all message's parts for text/*
  for msg in message.walk():
    if 'text' in msg.get_content_maintype():
      # Get the payload and decode (base64 & quoted printable)
      payload = msg.get_payload(decode=True)
      if not(isinstance(payload, unicode)):
        # What about other encodings? -> using chardet
        if msg.get_content_charset() is None:
          found = chardet.detect(payload)
          payload = payload.decode(found['encoding'])
        else:
          payload = payload.decode(msg.get_content_charset())

      # Check if our reply marker exist, save the payload in content Dict
      if marker in payload:
        content[msg.get_content_subtype()] = payload

  if len(content) == 0:
    logger.error('No marker:{} in email'.format(marker))
    raise LookupError('No marker:{} in email'.format(marker))

  # Extract post content (prioritize the use of html over plain)
  if 'html' in content:
    newpost = extract_content(content['html'], marker[:9])
    newpost = add_paragraph(validate_html(newpost))
  elif 'plain' in content:
    newpost = extract_content(content['plain'], marker)
    newpost = add_paragraph(newpost)
  else:
    # Error, bogus message, no text/* part or no marker was found
    logger.error('No text/ part in email')
    raise LookupError('No text/ part in email')

  return newpost


@celery.task(ignore_result=True)
def process_email(message):
  """
    email.message object from command line script
    Run message (parsed email) processing chain
    extract community thread post member from reply_to
    persist post in db
  """

  # Extract post destination from To field, (community/forum/thread/member)
  to_address = message['To']
  # Check if to_address has the subtag
  if not (has_subtag(to_address)):
    logger.info('Email {} has no subtag, skipping...'.format(to_address))
    return False
  try:
    infos = extract_email_destination(to_address)
    locale = infos[0]
    thread_id = infos[1]
    user_id = infos[2]
  except:
    logger.error('Email {} cannot be converted to locale/thread_id/user.id'.format(to_address))
    return False
  # Translate marker with locale from email address
  with current_app.test_request_context('/process_email', headers=[('Accept-Language', locale)]):
    marker = unicode(MAIL_REPLY_MARKER)
  # Extract text from message
  try:
    newpost = process(message, marker)
  except Exception as excp:
    logger.error('Could not Process message')
    logger.error(excp)
    return False

  # Persist post
  with current_app.test_request_context('/process_email'):
    g.user = User.query.get(user_id)
    thread = Thread.query.get(thread_id)
    post = thread.create_post(body_html=newpost)
    db.session.commit()

  # Notify all parties involved
  send_post_by_email.delay(post.id)

  return True


@periodic_task(run_every=crontab(minute='*', ), ignore_result=True)
def check_maildir():
  """
    check the MailDir for emails to be injected in Threads
  """

  home = expanduser("~")
  maildirpath = str(Path(home) / 'Maildir')
  src_mdir = mailbox.Maildir(maildirpath,
                             factory=mailbox.MaildirMessage)

  src_mdir.lock()  # Useless but recommended if old mbox is used by error

  try:
      for key, message in src_mdir.iteritems():
          processed = process_email(message)

          # delete the message if all went fine
          if processed:
            del src_mdir[key]

  finally:
      src_mdir.close()  # Flushes all changes to disk then unlocks
