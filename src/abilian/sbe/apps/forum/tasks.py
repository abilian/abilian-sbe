# Copyright (c) 2012-2024, Abilian SAS

"""Dramatiq tasks related to document transformation and preview."""

from __future__ import annotations

import email
import email.errors
import mailbox
import re
import smtplib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import chardet
import html2text
from filelock import FileLock, Timeout
from flask import current_app
from flask_babel import get_locale
from flask_mail import Message
from itsdangerous import Serializer
from loguru import logger

from abilian.core.dramatiq.scheduler import crontab
from abilian.core.dramatiq.setup import RATE_LIMITER
from abilian.core.dramatiq.singleton import dramatiq
from abilian.core.extensions import db, mail
from abilian.core.models.subjects import User
from abilian.core.signals import activity
from abilian.core.util import md5, unwrap
from abilian.i18n import _l, render_template_i18n
from abilian.sbe.apps.communities.security import is_member
from abilian.web import url_for
from abilian.web.rich_text import sanitize_html

from .models import Post, PostAttachment, Thread

if TYPE_CHECKING:
    from collections.abc import Callable

MAIL_REPLY_MARKER = _l("_____Write above this line to post_____")

#: Members mailed by one `batch_send_post_to_users` task.
CHUNK_SIZE = 20
#: Wait before mailing again the members a batch could not reach: 5 minutes.
RETRY_DELAY_MS = 300_000

MAILDIR_LOCK_FILE = ".check_maildir.lock"
PROCESSING_FOLDER = "processing"
REJECTED_FOLDER = "rejected"


class MailNotSentError(Exception):
    """No member of a batch could be mailed: the batch is to be retried."""


@dramatiq.actor(max_retries=20, max_backoff=86400000)
def send_post_by_email(post_id: int | str) -> None:
    """Send a post to community members by email.

    max_retries = 20 (Dramatiq default)
    max_backoff = 86400000 , i.e. 1 day
    """
    with current_app.test_request_context("/tasks/send_post_by_email"):
        post = Post.query.get(post_id)
        if post is None:
            # deleted after task queued, but before task run
            return

        thread = post.thread
        community = thread.community
        logger.info(
            "Sending new post by email to members of community {community}",
            community=repr(community.name),
        )

        # One message per batch, so that a batch that fails is retried alone.
        members_id = [member.id for member in community.members if member.can_login]
        for start in range(0, len(members_id), CHUNK_SIZE):
            chunk = members_id[start : start + CHUNK_SIZE]
            batch_send_post_to_users.send(post.id, chunk)


@dramatiq.actor(max_retries=20, max_backoff=86400000)
def batch_send_post_to_users(post_id: int, members_id: list[int]) -> None:
    """Send a post to a batch of members, retrying those it could not reach.

    Task run from `send_post_by_email`. The rate limiter allows 6 batches a
    minute. A retry must not mail a member twice, so a batch that reached only
    some members queues a new batch for the others; a batch that reached nobody
    raises, and Dramatiq retries it with an exponential backoff.
    """
    if not members_id:
        return

    post = Post.query.get(post_id)
    if post is None:
        # deleted after task queued, but before task run
        return

    with RATE_LIMITER[0].acquire():
        community = post.thread.community
        users = User.query.filter(User.id.in_(members_id)).all()
        failed = []
        for user in users:
            try:
                with current_app.test_request_context("/send_post_by_email"):
                    send_post_to_user(community, post, user)
            except (smtplib.SMTPException, OSError) as e:
                logger.error(
                    "Sending post {post_id} to user {user_id} failed: {error}",
                    post_id=post_id,
                    user_id=user.id,
                    error=str(e),
                )
                failed.append(user.id)

    if not failed:
        return
    if len(failed) == len(users):
        msg = f"Could not send post {post_id} to any of {failed}"
        raise MailNotSentError(msg)
    batch_send_post_to_users.send_with_options(
        args=(post_id, failed), delay=RETRY_DELAY_MS
    )


def build_local_part(name, uid):
    """Build local part as 'name-uid-digest', ensuring length < 64."""
    key = current_app.config["SECRET_KEY"]
    serializer = Serializer(key)
    signature = serializer.dumps(uid)
    digest = md5(signature)
    local_part = f"{name}+{uid}-{digest}"

    if len(local_part) > 64:
        if (len(local_part) - len(digest) - 1) > 64:
            # even without digest, it's too long
            msg = "Cannot build reply address: local part exceeds 64 characters"
            raise ValueError(msg)
        local_part = local_part[:64]

    return local_part


def build_reply_email_address(name: str, post: Post, member: User, domain: str) -> str:
    """Build a reply-to email address embedding the locale, thread_id and
    user.id.

    :param name: (str)    first part of an email address
    :param post: Post()   to get post.thread_id
    :param member: User() to get user.id
    :param domain: (str)  the last domain name of the email address
    :return: (Unicode)    reply address for forum in the form
       test+P-fr-3-4-SDB7T5DXNZPD5YAHHVIKVOE2PM@testcase.app.tld

       'P' for 'post' - locale - thread id - user id - signature digest
    """
    locale = get_locale()
    uid = "-".join(["P", str(locale), str(post.thread_id), str(member.id)])
    local_part = build_local_part(name, uid)
    return f"{local_part}@{domain}"


def extract_email_destination(address: str) -> tuple[str, ...]:
    """Return the values encoded in the email address.

    :param address: similar to test+IjEvMy8yLzQi.xjE04-4S0IzsdicTHKTAqcqa1fE@testcase.app.tld
    :return: List() of splitted values
    """
    m = re.search(r"<(.*)>", address)
    if m:
        address = m.group(1)
    local_part = address.rsplit("@", 1)[0]
    name, ident = local_part.rsplit("+", 1)
    uid, _digest = ident.rsplit("-", 1)
    signed_local_part = build_local_part(name, uid)

    if local_part != signed_local_part:
        msg = "Invalid signature in reply address"
        raise ValueError(msg)

    values = uid.split("-")
    header = values.pop(0)
    assert header == "P"
    return tuple(values)


def has_subtag(address: str) -> bool:
    """Return True if a subtag (delimited by '+') was found
    in the name part of the address.

    :param address: email adress
    """
    name = address.rsplit("@", 1)[0]
    return "+" in name


def send_post_to_user(community, post, member) -> None:
    """Send a post though SMTP.

    Configuring Flask-Mail
    Flask-Mail is configured through the standard Flask config API.
    These are the available options:

    MAIL_SERVER : default 'localhost'
    MAIL_PORT : default 25
    MAIL_USE_TLS : default False
    MAIL_USE_SSL : default False
    MAIL_DEBUG : default app.debug
    MAIL_USERNAME : default None
    MAIL_PASSWORD : default None
    MAIL_DEFAULT_SENDER : default None
    MAIL_MAX_EMAILS : default None
    MAIL_SUPPRESS_SEND : default app.testing
    MAIL_ASCII_ATTACHMENTS : default False
    """

    message = _mail_from_post(community, post, member)

    logger.info(
        "Sending new post by email to {recipients}",
        recipients=message.recipients,
    )
    # Errors propagate: the batch that called us retries the recipient.
    with current_app.app_context():
        mail.send(message)


def _mail_from_post(community, post, member) -> Message:
    """Return a mail.Message build from a post in community forum"""
    recipient = member.email
    subject = f"[{community.name}] {post.title}"
    logger.debug(
        "subject={subject} recipient={recipient}",
        subject=subject,
        recipient=recipient,
    )

    config = current_app.config
    SENDER = config.get("BULK_MAIL_SENDER", config["MAIL_SENDER"])
    SBE_FORUM_REPLY_BY_MAIL = config.get("SBE_FORUM_REPLY_BY_MAIL", False)
    SBE_FORUM_REPLY_ADDRESS = config.get("SBE_FORUM_REPLY_ADDRESS", SENDER)
    SERVER_NAME = config.get("SERVER_NAME", "example.com")

    list_id = f'"{community.name} forum" <forum.{community.slug}.{SERVER_NAME}>'
    forum_url = url_for("forum.index", community_id=community.slug, _external=True)
    forum_archive_url = url_for(
        "forum.archives", community_id=community.slug, _external=True
    )
    extra_headers = {
        "List-Id": list_id,
        "List-Archive": f"<{forum_archive_url}>",
        "List-Post": f"<{forum_url}>",
        "X-Auto-Response-Suppress": "All",
        "Auto-Submitted": "auto-generated",
    }

    if SBE_FORUM_REPLY_BY_MAIL:
        name = SBE_FORUM_REPLY_ADDRESS.rsplit("@", 1)[0]
        domain = SBE_FORUM_REPLY_ADDRESS.rsplit("@", 1)[1]
        reply_to = build_reply_email_address(name, post, member, domain)
        sender = SBE_FORUM_REPLY_ADDRESS
    else:
        sender = SENDER
        reply_to = None

    msg = Message(
        subject,
        recipients=[recipient],
        sender=sender,
        reply_to=reply_to,
        extra_headers=extra_headers,
    )

    ctx = {
        "community": community,
        "post": post,
        "member": member,
        "MAIL_REPLY_MARKER": MAIL_REPLY_MARKER,
        "SBE_FORUM_REPLY_BY_MAIL": SBE_FORUM_REPLY_BY_MAIL,
    }
    msg.html = render_template_i18n("forum/mail/new_message.html", **ctx)
    msg.body = html2text.html2text(msg.html)
    return msg


def extract_content(payload, marker):
    """Search the payload for marker, return content up to marker."""
    index = payload.rfind(marker)
    content = payload[:index]
    return content


def add_paragraph(newpost):
    """Add surrounding <p>newpost</p> if necessary."""
    newpost = newpost.strip()
    if not newpost.startswith("<p>"):
        newpost = f"<p>{newpost}</p>"
    return newpost


def clean_html(newpost: str) -> str:
    """Clean leftover empty blockquotes."""

    clean = re.sub(
        r"(<blockquote.*?<p>.*?</p>.*?</blockquote>)",
        "",
        newpost,
        flags=re.MULTILINE | re.DOTALL,
    )

    # this cleans auto generated reponse text (<br>timedate <a email /a><br>)
    # we reverse the string because re.sub replaces
    #  LEFTMOST NON-OVERLAPPING OCCURRENCES, and we only want the last match
    # in the string
    clean = re.sub(
        r"(>rb<.*?>a.*?=ferh\sa<.*?>rb<)",
        "",
        clean[::-1],
        flags=re.MULTILINE | re.DOTALL,
    )
    clean = clean[::-1]

    return clean


def decode_payload(part: email.message.Message) -> str:
    """Get the payload and decode (base64 & quoted printable)."""

    payload = part.get_payload(decode=True)

    if isinstance(payload, str):
        return payload

    # Please the typechecker (and make things a bit clearer)
    assert isinstance(payload, bytes)
    payload_bytes: bytes = payload

    charset = part.get_content_charset()
    if charset is not None:
        try:
            payload_str = payload_bytes.decode(charset)
        except UnicodeDecodeError:
            payload_str = payload_bytes.decode("raw-unicode-escape")
    else:
        # What about other encodings? -> using chardet
        found = chardet.detect(payload_bytes)
        payload_str = payload_bytes.decode(found["encoding"])

    return payload_str


def process(message: email.message.Message, marker: str) -> tuple[str, list[dict]]:
    """Check the message for marker presence and return the text up to it if
    present.

    :raises LookupError otherwise.
    :return: sanitized html upto marker from message and attachements
    """
    assert isinstance(message, email.message.Message)
    content = {"plain": "", "html": ""}
    attachments: list[dict[str, Any]] = []

    # Iterate all message's parts for text/*
    for part in message.walk():
        content_type = part.get_content_type()
        content_disposition = part.get("Content-Disposition")

        if content_disposition not in [None, "inline"]:
            attachments.append(
                {
                    "filename": part.get_filename(),
                    "content_type": part.get_content_type(),
                    "data": part.get_payload(decode=True),
                }
            )

        elif content_type in ["text/plain", "text/html"]:
            subtype = part.get_content_subtype()
            payload = decode_payload(part)
            content[subtype] += payload

    if marker in content["html"]:
        newpost = extract_content(content["html"], marker[:9])
        newpost = add_paragraph(sanitize_html(newpost))
        newpost = clean_html(newpost)
    elif marker in content["plain"]:
        newpost = extract_content(content["plain"], marker[:9])
        newpost = add_paragraph(newpost)
    elif content["html"]:
        newpost = content["html"]
        newpost = add_paragraph(sanitize_html(newpost))
        newpost = clean_html(newpost)
    else:
        newpost = content["plain"]
        newpost = add_paragraph(newpost)
    # else:
    #     raise LookupError(f"No marker:{marker} in email")

    return newpost, attachments


@dramatiq.actor(max_retries=20, max_backoff=86400000)
def process_email(message: str | email.message.Message) -> bool:
    """Post a reply received by email to the thread its address names.

    A message queued by `flask inject_email` arrives as a string, since a
    Dramatiq message must be JSON; a direct call may pass the parsed message.
    The destination (locale, thread, member) is read from the signed `To:`
    address. Return False if the message is rejected.
    """
    if isinstance(message, str):
        message = email.message_from_string(message)
    app = unwrap(current_app)
    # Extract post destination from To: field, (community/forum/thread/member)
    to_address = message["To"]

    assert isinstance(to_address, str)

    if not (has_subtag(to_address)):
        logger.info(
            "Email {to_address} has no subtag, skipping...",
            to_address=repr(to_address),
        )
        return False

    try:
        infos = extract_email_destination(to_address)
        locale = infos[0]
        thread_id = infos[1]
        user_id = infos[2]
    except BaseException:
        logger.opt(exception=True).error(
            "Recipient {to_address} cannot be converted to locale/thread_id/user.id",
            to_address=repr(to_address),
        )
        return False

    # Translate marker with locale from email address
    rq_headers = [("Accept-Language", locale)]
    with app.test_request_context("/process_email", headers=rq_headers):
        marker = str(MAIL_REPLY_MARKER)

    # Extract text and attachments from message
    try:
        newpost, attachments = process(message, marker)
    except (LookupError, ValueError, email.errors.MessageError):
        logger.opt(exception=True).error("Could not Process message")
        return False

    # Persist post
    with current_app.test_request_context("/process_email", headers=rq_headers):
        user = User.query.get(user_id)
        thread = Thread.query.get(thread_id)
        if thread is None:
            # Deleted since the notification went out: retrying cannot help.
            logger.warning(
                "Reply to a thread that no longer exists: {thread_id}",
                thread_id=thread_id,
            )
            return False
        community = thread.community
        # The address is signed, but it outlives a membership: whoever left the
        # community, or was removed from it, still has the e-mails it came in.
        # TODO: tell them, by e-mail, that the reply was not posted.
        if user is None or not is_member(user, community):
            logger.warning(
                "Reply by a non-member to thread {thread_id}, dropped",
                thread_id=thread_id,
            )
            return False
        post = thread.create_post(body_html=newpost, creator=user, owner=user)
        obj_meta = post.meta.setdefault("abilian.sbe.forum", {})
        obj_meta["origin"] = "email"
        obj_meta["send_by_email"] = True
        activity.send(app, actor=user, verb="post", object=post, target=community)

        for desc in attachments:
            filename = desc["filename"]
            content_type = desc["content_type"]
            data = desc["data"]
            if isinstance(data, str):
                data = data.encode("utf8")
            attachment = PostAttachment(name=filename)
            attachment.post = post
            attachment.set_content(data, content_type=content_type)
            db.session.add(attachment)

        db.session.commit()

    # Notify all parties involved
    send_post_by_email.send(post.id)
    return True


@crontab("SCHEDULE_CHECK_MAILDIR")
@dramatiq.actor(max_retries=20, max_backoff=86400000)
def check_maildir() -> None:
    """Check the MailDir for emails to be injected in Threads.

    Scheduled only if `INCOMING_MAIL_USE_MAILDIR` is True, every minute by
    default (`SCHEDULE_CHECK_MAILDIR`).
    """
    maildir_path = Path.home() / "Maildir"
    if not maildir_path.is_dir():
        msg = f"{maildir_path} must be a directory"
        raise ValueError(msg)

    drain_maildir(maildir_path, process_email)


def drain_maildir(
    maildir_path: Path, post: Callable[[email.message.Message], bool]
) -> None:
    """Hand every new message of the Maildir to `post`, at most once.

    `Maildir.lock()` does nothing, so a file lock keeps two runs (an overlap,
    or a retry) from reading the same messages; a run that finds it held does
    nothing. Each message moves to the `processing` folder before it is posted:
    a run that fails after posting cannot post it again. It stays there, for an
    admin to look at. A message `post` rejects moves to the `rejected` folder,
    instead of being read again every minute.
    """
    lock = FileLock(maildir_path / MAILDIR_LOCK_FILE)
    try:
        lock.acquire(blocking=False)
    except Timeout:
        logger.info("{path} is being checked already, skipping", path=maildir_path)
        return

    try:
        inbox = mailbox.Maildir(maildir_path, create=False)
        processing = inbox.add_folder(PROCESSING_FOLDER)
        rejected = inbox.add_folder(REJECTED_FOLDER)
        # A list, read once: the loop takes the messages out of the inbox.
        for key, new_message in inbox.items():
            processing_key = processing.add(new_message)
            inbox.discard(key)
            message = processing[processing_key]
            if not post(message):
                rejected.add(message)
            processing.discard(processing_key)
    finally:
        lock.release()
