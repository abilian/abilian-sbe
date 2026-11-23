# Copyright (c) 2012-2024, Abilian SAS

"""The forum's mail tasks: posts mailed to members, replies read from a Maildir."""

from __future__ import annotations

import email
import mailbox
import smtplib
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from dramatiq import Message
from filelock import FileLock

from abilian.core.extensions import mail
from abilian.core.models.subjects import User
from abilian.sbe.apps.communities.models import MEMBER
from abilian.sbe.apps.forum import tasks
from abilian.sbe.apps.forum.cli import inject_email
from abilian.sbe.apps.forum.tasks import (
    MAILDIR_LOCK_FILE,
    MailNotSentError,
    batch_send_post_to_users,
    build_reply_email_address,
    drain_maildir,
    process_email,
    send_post_by_email,
)
from tests.forum_util import get_string_from_file, started_thread

if TYPE_CHECKING:
    from pathlib import Path

    from dramatiq.brokers.stub import StubBroker
    from flask import Flask

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.sbe.apps.communities.models import Community


class Poster:
    """Stands for `process_email`: records the subjects it is handed."""

    def __init__(self, *, accept: bool = True, fail: bool = False) -> None:
        self.accept = accept
        self.fail = fail
        self.posted: list[str] = []

    def __call__(self, message: email.message.Message) -> bool:
        self.posted.append(message["Subject"])
        if self.fail:
            # As a run that posted, then failed before taking the message out.
            msg = "the task broker is down"
            raise ConnectionError(msg)
        return self.accept


@pytest.fixture
def maildir(tmp_path: Path) -> Path:
    path = tmp_path / "Maildir"
    inbox = mailbox.Maildir(path)
    inbox.add(email.message_from_string("Subject: Hello\n\nA reply.\n"))
    return path


def test_a_message_is_posted_once_over_two_runs(maildir: Path) -> None:
    poster = Poster()

    drain_maildir(maildir, poster)
    drain_maildir(maildir, poster)

    assert poster.posted == ["Hello"]
    assert not mailbox.Maildir(maildir).keys()


def test_a_run_skips_a_maildir_another_run_is_checking(maildir: Path) -> None:
    poster = Poster()

    with FileLock(maildir / MAILDIR_LOCK_FILE):
        drain_maildir(maildir, poster)

    assert poster.posted == []
    assert len(mailbox.Maildir(maildir)) == 1


def test_a_retry_does_not_post_again_a_message_a_failed_run_posted(
    maildir: Path,
) -> None:
    with pytest.raises(ConnectionError):
        drain_maildir(maildir, Poster(fail=True))
    poster = Poster()

    drain_maildir(maildir, poster)

    assert poster.posted == []
    processing = mailbox.Maildir(maildir).get_folder(tasks.PROCESSING_FOLDER)
    assert [m["Subject"] for m in processing] == ["Hello"]


def test_a_rejected_message_is_set_aside_not_read_again(maildir: Path) -> None:
    poster = Poster(accept=False)

    drain_maildir(maildir, poster)
    drain_maildir(maildir, poster)

    assert poster.posted == ["Hello"]
    inbox = mailbox.Maildir(maildir)
    assert not inbox.keys()
    rejected = inbox.get_folder(tasks.REJECTED_FOLDER)
    assert [m["Subject"] for m in rejected] == ["Hello"]


# Posts mailed to members


@pytest.fixture
def broker(app: Flask) -> StubBroker:
    broker = batch_send_post_to_users.broker
    broker.flush_all()
    return broker


def queued(broker: StubBroker, queue_name: str) -> list[Message]:
    return [Message.decode(data) for data in broker.queues[queue_name].queue]


def members(db: SQLAlchemy, community: Community, count: int) -> list[User]:
    users = [
        User(email=f"member{i}@example.com", password="x", can_login=True)  # noqa: S106
        for i in range(count)
    ]
    db.session.add_all(users)
    for user in users:
        community.set_membership(user, MEMBER)
    db.session.commit()
    return users


def test_a_post_is_mailed_in_full_batches(
    app: Flask, db: SQLAlchemy, community1: Community, broker: StubBroker
) -> None:
    members(db, community1, tasks.CHUNK_SIZE)  # plus the community's test user
    thread = started_thread(db, community1, community1.test_user, "Budget")

    send_post_by_email(thread.posts[0].id)

    batches = [m.args[1] for m in queued(broker, "default")]
    assert [len(batch) for batch in batches] == [tasks.CHUNK_SIZE, 1]


def refusing(refused: set[str], sent: list[str]):
    """A `mail.send` that refuses the addresses in `refused`."""

    def send(message) -> None:
        (recipient,) = message.recipients
        if recipient in refused:
            raise smtplib.SMTPRecipientsRefused({recipient: (550, b"No")})
        sent.append(recipient)

    return send


def test_a_batch_mails_again_only_the_members_it_could_not_reach(
    app: Flask, db: SQLAlchemy, community1: Community, broker: StubBroker
) -> None:
    alice, bob = members(db, community1, 2)
    thread = started_thread(db, community1, alice, "Budget")
    sent: list[str] = []

    with mock.patch.object(mail, "send", refusing({bob.email}, sent)):
        batch_send_post_to_users(thread.posts[0].id, [alice.id, bob.id])

    assert sent == [alice.email]
    (retry,) = queued(broker, "default.DQ")
    assert retry.args[1] == [bob.id]


def test_a_batch_that_reaches_nobody_fails_to_be_retried(
    app: Flask, db: SQLAlchemy, community1: Community, broker: StubBroker
) -> None:
    (alice,) = members(db, community1, 1)
    thread = started_thread(db, community1, alice, "Budget")

    with (
        mock.patch.object(mail, "send", refusing({alice.email}, [])),
        pytest.raises(MailNotSentError),
    ):
        batch_send_post_to_users(thread.posts[0].id, [alice.id])


# Replies by email


def reply_to(app: Flask, thread, user: User) -> str:
    message = email.message_from_string(get_string_from_file("notification.email"))
    post = mock.Mock(id=1, thread_id=thread.id)
    with app.test_request_context():
        address = build_reply_email_address("test", post, user, "example.com")
    message.replace_header("To", address)
    return message.as_string()


def test_a_reply_queued_as_text_is_posted_by_its_author(
    app: Flask, db: SQLAlchemy, community1: Community, broker: StubBroker
) -> None:
    user = community1.test_user
    community1.set_membership(user, MEMBER)
    thread = started_thread(db, community1, user, "Budget 2027")
    thread_id, user_id = thread.id, user.id

    assert process_email(reply_to(app, thread, user)) is True

    db.session.expire_all()
    reply = db.session.get(tasks.Thread, thread_id).posts[-1]
    assert reply.creator_id == user_id


def test_inject_email_queues_the_message_as_text(
    app: Flask, db: SQLAlchemy, broker: StubBroker
) -> None:
    raw = get_string_from_file("notification.email")

    result = app.test_cli_runner().invoke(inject_email, input=raw)

    assert result.exit_code == 0, result.output
    (message,) = queued(broker, "default")
    assert message.actor_name == "process_email"
    assert message.args[0] == email.message_from_string(raw).as_string()


@pytest.mark.parametrize("filename", ["defects.email", None])
def test_inject_email_fails_on_a_message_it_cannot_read(
    app: Flask, db: SQLAlchemy, broker: StubBroker, filename: str | None
) -> None:
    raw = get_string_from_file(filename) if filename else ""

    result = app.test_cli_runner().invoke(inject_email, input=raw)

    assert result.exit_code != 0
    assert not broker.queues["default"].queue
