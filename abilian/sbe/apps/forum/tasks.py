# coding=utf-8
"""
Celery tasks related to document transformation and preview.
"""
from __future__ import absolute_import

import mailbox
from os.path import expanduser
import re

import bleach
import chardet
from pathlib import Path
from itsdangerous import URLSafeSerializer
from flask import current_app, g
from flask.ext.mail import Message
from flask.ext.babel import get_locale
from celery import shared_task
from abilian.core.celery import periodic_task
from celery.utils.log import get_task_logger
from celery.schedules import crontab

from abilian.core.signals import activity
from abilian.core.extensions import mail, db
from abilian.core.models.subjects import User
from abilian.i18n import _l, render_template_i18n

from .forms import ALLOWED_ATTRIBUTES, ALLOWED_TAGS
from .models import Thread, PostAttachment


MAIL_REPLY_MARKER = _l(u'_____Write above this line to post_____')

# logger = logging.getLogger(__package__)
# Celery logger
logger = get_task_logger(__name__)


def init_app(app):
  global check_maildir
  if app.config['INCOMING_MAIL_USE_MAILDIR']:
    make_task = periodic_task(run_every=crontab(minute='*', ),
                             ignore_result=True)
    check_maildir = make_task(check_maildir)


@shared_task(ignore_result=True)
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
    SBE_FORUM_REPLY_BY_MAIL=SBE_FORUM_REPLY_BY_MAIL, )
  msg.html = render_template_i18n(
    "forum/mail/new_message.html",
    community=community, post=post, member=member,
    MAIL_REPLY_MARKER=MAIL_REPLY_MARKER,
    SBE_FORUM_REPLY_BY_MAIL=SBE_FORUM_REPLY_BY_MAIL, )

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


def clean_html(newpost):
  clean = re.sub(r"(<blockquote.*?<p>.*?</p>.*?</blockquote>)", '', newpost, flags=re.MULTILINE | re.DOTALL)
  clean = re.sub(r"(<br>.*?<a href=.*?/a>.*?:<br>)", '', clean, flags=re.MULTILINE | re.DOTALL)
  return clean


def decode_payload(part):
  # Get the payload and decode (base64 & quoted printable)
  payload = part.get_payload(decode=True)
  if not (isinstance(payload, unicode)):
    # What about other encodings? -> using chardet
    if part.get_content_charset() is None:
      found = chardet.detect(payload)
      payload = payload.decode(found['encoding'])
    else:
      payload = payload.decode(part.get_content_charset())
  return payload


def process(message, marker):
  """
    Check the message for marker presence and return the text up to it if present
    :raises LookupError otherwise.
    :param message: email.Message()
    :param marker: unicode
    :return: sanitized html upto marker from message
  """
  content = {'plain': u'', 'html': u''}
  attachments = []
  # Iterate all message's parts for text/*
  for part in message.walk():
    content_type = part.get_content_type()
    content_disp = part.get('Content-Disposition')

    if content_type in ['text/plain', 'text/html'] and content_disp is None:
      payload = content[part.get_content_subtype()] + decode_payload(part)
      content[part.get_content_subtype()] = payload

    if content_disp is not None:
      attachments.append(
        {'filename': part.get_filename(),
         'content_type': part.get_content_type(),
         'data': part.get_payload(decode=True)})

  if 'html' in content and marker in content['html']:
    newpost = extract_content(content['html'], marker[:9])
    newpost = add_paragraph(validate_html(newpost))
    newpost = clean_html(newpost)
  elif 'plain' in content and marker in content['plain']:
    newpost = extract_content(content['plain'], marker[:9])
    newpost = add_paragraph(newpost)
  else:
    logger.error('No marker:{} in email'.format(marker))
    raise LookupError('No marker:{} in email'.format(marker))

  return newpost, attachments


@shared_task(ignore_result=True)
def process_email(message):
  """
  Email.Message object from command line script Run message (parsed email).

  Processing chain extract community thread post member from reply_to persist
  post in db
  """
  app = current_app._get_current_object()
  # Extract post destination from To: field, (community/forum/thread/member)
  to_address = message['To']

  if not (has_subtag(to_address)):
    logger.info('Email {} has no subtag, skipping...'.format(to_address))
    return False

  try:
    infos = extract_email_destination(to_address)
    locale = infos[0]
    thread_id = infos[1]
    user_id = infos[2]
  except:
    logger.error('Recipient %s cannot be converted to locale/thread_id/user.id',
                 repr(to_address))
    return False

  # Translate marker with locale from email address
  rq_headers = [('Accept-Language', locale)]
  with app.test_request_context('/process_email', headers=rq_headers):
    marker = unicode(MAIL_REPLY_MARKER)

  # Extract text and attachments from message
  try:
    newpost, attachments = process(message, marker)
  except Exception as excp:
    logger.error('Could not Process message')
    logger.error(excp)
    return False

  # Persist post
  with current_app.test_request_context('/process_email', headers=rq_headers):
    g.user = User.query.get(user_id)
    thread = Thread.query.get(thread_id)
    community = thread.community
    # FIXME: check membership, send back an informative email in case of an error
    post = thread.create_post(body_html=newpost)
    activity.send(app, actor=g.user, verb='post', object=post, target=community)

    if len(attachments) > 0:
      for desc in attachments:
        attachment = PostAttachment(name=desc['filename'])
        attachment.post = post
        attachment.set_content(desc['data'], desc['content_type'])
        db.session.add(attachment)
    db.session.commit()

  # Notify all parties involved
  send_post_by_email.delay(post.id)
  return True


def check_maildir():
  """
  Check the MailDir for emails to be injected in Threads.

  This task is registered only if `INCOMING_MAIL_USE_MAILDIR` is True. By
  default it is run every minute.
  """
  home = expanduser('~')
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
