# coding=utf-8
"""
Celery tasks related to document transformation and preview.
"""
from __future__ import absolute_import

import base64
import hashlib
import mailbox
import re
from os.path import expanduser

import bleach
import chardet
from celery import shared_task
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from flask import current_app, g
from flask_babel import get_locale
from flask_mail import Message
from itsdangerous import Serializer
from pathlib import Path

from abilian.core.celery import periodic_task
from abilian.core.extensions import db, mail
from abilian.core.models.subjects import User
from abilian.core.signals import activity
from abilian.i18n import _l, render_template_i18n
from abilian.web import url_for

from .forms import ALLOWED_ATTRIBUTES, ALLOWED_STYLES, ALLOWED_TAGS
from .models import PostAttachment, Thread

MAIL_REPLY_MARKER = _l(u'_____Write above this line to post_____')

# logger = logging.getLogger(__package__)
# Celery logger
logger = get_task_logger(__name__)


def init_app(app):
    global check_maildir
    if app.config['INCOMING_MAIL_USE_MAILDIR']:
        make_task = periodic_task(run_every=crontab(minute='*',),)
        check_maildir = make_task(check_maildir)


@shared_task()
def send_post_by_email(post_id):
    """Send a post to community members by email."""
    from .models import Post

    with current_app.test_request_context('/send_post_by_email'):
        post = Post.query.get(post_id)
        if post is None:
            # deleted after task queued, but before task run
            return

        thread = post.thread
        community = thread.community
        logger.info("Sending new post by email to members of community %r",
                    community.name)

        CHUNK_SIZE = 20
        members_id = [member.id
                      for member in community.members if member.can_login]
        chunk = []
        for idx, member_id in enumerate(members_id):
            chunk.append(member_id)
            if idx % CHUNK_SIZE == 0:
                batch_send_post_to_users.apply_async((post.id, chunk))
                chunk = []

        if chunk:
            batch_send_post_to_users.apply_async((post.id, chunk))


@shared_task(max_retries=10, rate_limit='12/m')
def batch_send_post_to_users(post_id, members_id, failed_ids=None):
    """
    Task run from send_post_by_email; auto-retry for mails that could not be
    successfully sent.

    Task default rate limit is 6/min.: there is at least 5 seconds between 2
    batches.

    During retry, if all `members_id` fails again, the task is retried
    5min. later, then 10, 20, 40... up to 10 times before giving up. This ensures
    retries up to approximatively 3 days and 13 hours after initial attempt
    (geometric series is: 5min * (1-2**10) / 1-2) = 5115 mins).
    """
    from .models import Post

    if not members_id:
        return

    post = Post.query.get(post_id)
    if post is None:
        # deleted after task queued, but before task run
        return

    failed = set()
    successfully_sent = []
    thread = post.thread
    community = thread.community
    user_filter = (User.id.in_(members_id) if len(members_id) > 1 else
                   User.id == members_id[0])
    users = User.query.filter(user_filter).all()

    for user in users:
        try:
            with current_app.test_request_context('/send_post_by_email'):
                send_post_to_user(community, post, user)
        except:
            failed.add(user.id)
        else:
            successfully_sent.append(user.id)

    if failed:
        if failed_ids is not None:
            failed_ids = set(failed_ids)

        if failed == failed_ids:
            # 5 minutes * (2** retry count)
            countdown = 300 * 2**batch_send_post_to_users.request.retries
            batch_send_post_to_users.retry(
                [post_id, list(failed)],
                countdown=countdown)
        else:
            batch_send_post_to_users.apply_async([post_id, list(failed)])

    return {'post_id': post_id,
            'successfully_sent': successfully_sent,
            'failed': list(failed),}


def build_local_part(name, uid):
    """
    Build local part as 'name-uid-digest', ensuring length < 64.
    """
    tag = current_app.config['MAIL_ADDRESS_TAG_CHAR']
    key = current_app.config['SECRET_KEY']
    serializer = Serializer(key)
    signature = serializer.dumps(uid.decode('utf-8'))
    digest = hashlib.md5(signature).digest()
    digest = base64.b32encode(digest).split('=', 1)[0]  # remove base32 padding
    digest = unicode(digest)
    local_part = name + tag + uid + u'-' + digest

    if len(local_part) > 64:
        if (len(local_part) - len(digest) - 1) > 64:
            # even without digest, it's too long
            raise ValueError(
                'Cannot build reply address: local part exceeds 64 '
                'characters')
        local_part = local_part[:64]

    return local_part


def build_reply_email_address(name, post, member, domain):
    """
    Build a reply-to email address embedding the locale, thread_id and user.id.

    :param name: (str)    first part of an email address
    :param post: Post()   to get post.thread_id
    :param member: User() to get user.id
    :param domain: (str)  the last domain name of the email address
    :return: (unicode)    reply address for forum in the form
    test+P-fr-3-4-SDB7T5DXNZPD5YAHHVIKVOE2PM@testcase.app.tld

    'P' for 'post' - locale - thread id - user id - signature digest
    """
    locale = get_locale()
    uid = u'-'.join([u'P', str(locale), str(post.thread_id), str(member.id)])
    local_part = build_local_part(name, uid)
    return local_part + u'@' + domain


def extract_email_destination(address):
    """Return the values encoded in the email address.

    :param address: similar to test+IjEvMy8yLzQi.xjE04-4S0IzsdicTHKTAqcqa1fE@testcase.app.tld
    :return: List() of splitted values
    """
    local_part = address.rsplit('@', 1)[0]
    tag = current_app.config['MAIL_ADDRESS_TAG_CHAR']
    name, ident = local_part.rsplit(tag, 1)
    uid, digest = ident.rsplit('-', 1)
    signed_local_part = build_local_part(name, uid)

    if local_part != signed_local_part:
        raise ValueError('Invalid signature in reply address')

    values = uid.split(u'-')
    header = values.pop(0)
    assert header == u'P'
    return values


def has_subtag(address):
    """Return True if a subtag (defined in the config.py as 'MAIL_ADDRESS_TAG_CHAR')
    was found in the name part of the address

    :param address: email adress
    :rtype: Boolean
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
    SERVER_NAME = config.get('SERVER_NAME', u'example.com')
    list_id = u'"{} forum" <forum.{}.{}>'.format(community.name, community.slug,
                                                 SERVER_NAME)
    forum_url = url_for('forum.index',
                        community_id=community.slug,
                        _external=True)
    forum_archive = url_for('forum.archives',
                            community_id=community.slug,
                            _external=True)

    extra_headers = {
        'List-Id': list_id,
        'List-Archive': u'<{}>'.format(forum_archive),
        'List-Post': '<{}>'.format(forum_url),
        'X-Auto-Response-Suppress': 'All',
        'Auto-Submitted': 'auto-generated',
    }

    if SBE_FORUM_REPLY_BY_MAIL and config['MAIL_ADDRESS_TAG_CHAR'] is not None:
        name = sender.rsplit('@', 1)[0]
        domain = sender.rsplit('@', 1)[1]
        replyto = build_reply_email_address(name, post, member, domain)
        msg = Message(subject,
                      sender=sender,
                      recipients=[recipient],
                      reply_to=replyto,
                      extra_headers=extra_headers)
    else:
        msg = Message(subject,
                      sender=sender,
                      recipients=[recipient],
                      extra_headers=extra_headers)

    msg.body = render_template_i18n(
        "forum/mail/new_message.txt",
        community=community,
        post=post,
        member=member,
        MAIL_REPLY_MARKER=MAIL_REPLY_MARKER,
        SBE_FORUM_REPLY_BY_MAIL=SBE_FORUM_REPLY_BY_MAIL,)
    msg.html = render_template_i18n(
        "forum/mail/new_message.html",
        community=community,
        post=post,
        member=member,
        MAIL_REPLY_MARKER=MAIL_REPLY_MARKER,
        SBE_FORUM_REPLY_BY_MAIL=SBE_FORUM_REPLY_BY_MAIL,)
    logger.debug("Sending new post by email to %r", member.email)

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
    return bleach.clean(payload,
                        tags=ALLOWED_TAGS,
                        attributes=ALLOWED_ATTRIBUTES,
                        styles=ALLOWED_STYLES,
                        strip=True).strip()


def add_paragraph(newpost):
    """Add surrounding <p>newpost</p> if necessary."""

    newpost = newpost.strip()
    if not newpost.startswith(u'<p>'):
        newpost = u'<p>' + newpost + u'</p>'
    return newpost


def clean_html(newpost):
    """Clean leftover empty blockquotes."""

    clean = re.sub(r"(<blockquote.*?<p>.*?</p>.*?</blockquote>)",
                   '',
                   newpost,
                   flags=re.MULTILINE | re.DOTALL)

    # this cleans auto generated reponse text (<br>timedate <a email /a><br>)
    # we reverse the string because re.sub replaces
    #  LEFTMOST NON-OVERLAPPING OCCURRENCES, and we only want the last match
    # in the string
    clean = re.sub(r"(>rb<.*?>a.*?=ferh\sa<.*?>rb<)",
                   '',
                   clean[::-1],
                   flags=re.MULTILINE | re.DOTALL)
    clean = clean[::-1]

    return clean


def decode_payload(part):
    """Get the payload and decode (base64 & quoted printable)."""

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
    Check the message for marker presence and return the text up to it if present.

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
            attachments.append({'filename': part.get_filename(),
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


@shared_task()
def process_email(message):
    """
    Email.Message object from command line script Run message (parsed email).

    Processing chain extract community thread post member from reply_to persist
    post in db.
    """
    app = current_app._get_current_object()
    # Extract post destination from To: field, (community/forum/thread/member)
    to_address = message['To']

    if not (has_subtag(to_address)):
        logger.info('Email %r has no subtag, skipping...', to_address)
        return False

    try:
        infos = extract_email_destination(to_address)
        locale = infos[0]
        thread_id = infos[1]
        user_id = infos[2]
    except:
        logger.error(
            'Recipient %r cannot be converted to locale/thread_id/user.id',
            to_address,
            exc_info=True)
        return False

    # Translate marker with locale from email address
    rq_headers = [('Accept-Language', locale)]
    with app.test_request_context('/process_email', headers=rq_headers):
        marker = unicode(MAIL_REPLY_MARKER)

    # Extract text and attachments from message
    try:
        newpost, attachments = process(message, marker)
    except:
        logger.error('Could not Process message', exc_info=True)
        return False

    # Persist post
    with current_app.test_request_context('/process_email', headers=rq_headers):
        g.user = User.query.get(user_id)
        thread = Thread.query.get(thread_id)
        community = thread.community
        # FIXME: check membership, send back an informative email in case of an error
        post = thread.create_post(body_html=newpost)
        obj_meta = post.meta.setdefault('abilian.sbe.forum', {})
        obj_meta['origin'] = u'email'
        obj_meta['send_by_email'] = True
        activity.send(app,
                      actor=g.user,
                      verb='post',
                      object=post,
                      target=community)

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
    """Check the MailDir for emails to be injected in Threads.

    This task is registered only if `INCOMING_MAIL_USE_MAILDIR` is True. By
    default it is run every minute.
    """
    home = expanduser('~')
    maildirpath = str(Path(home) / 'Maildir')
    src_mdir = mailbox.Maildir(maildirpath, factory=mailbox.MaildirMessage)

    src_mdir.lock()  # Useless but recommended if old mbox is used by error

    try:
        for key, message in src_mdir.iteritems():
            processed = process_email(message)

            # delete the message if all went fine
            if processed:
                del src_mdir[key]

    finally:
        src_mdir.close()  # Flushes all changes to disk then unlocks
