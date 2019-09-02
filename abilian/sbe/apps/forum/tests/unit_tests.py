import pytest
from pytest import raises

from abilian.sbe.apps.forum.tests.util import get_email_message_from_file

from ..models import Post, Thread, ThreadClosedError
from ..tasks import process


def test_create_post():
    thread = Thread(title="Test thread")
    post = thread.create_post()
    assert post in thread.posts
    assert post.name == "Test thread"

    thread.title = "new title"
    assert thread.name == "new title"
    assert post.name == "new title"


def test_closed_property():
    thread = Thread(title="Test Thread")
    assert thread.closed is False
    thread.closed = True
    assert thread.closed is True
    thread.closed = 0
    assert thread.closed is False
    thread.closed = 1
    assert thread.closed is True
    assert thread.meta["abilian.sbe.forum"]["closed"] is True


def test_thread_closed_guard():
    thread = Thread(title="Test Thread")
    thread.create_post()
    thread.closed = True

    with pytest.raises(ThreadClosedError):
        thread.create_post()

    p = Post(body_html="ok")

    with pytest.raises(ThreadClosedError):
        p.thread = thread

    thread.closed = False
    p.thread = thread
    assert len(thread.posts) == 2

    thread.closed = True
    with pytest.raises(ThreadClosedError):
        del thread.posts[0]

    assert len(thread.posts) == 2

    with pytest.raises(ThreadClosedError):
        # actually thread.posts will be replaced by `[]` and we can't prevent
        # this, but exception has been raised
        thread.posts = []

    thread.closed = False
    thread.posts = [p]
    thread.closed = True
    assert thread.posts == [p]
    assert p.thread is thread
    with pytest.raises(ThreadClosedError):
        p.thread = None


def test_change_thread_copy_name():
    thread = Thread(title="thread 1")
    thread2 = Thread(title="thread 2")
    post = Post(thread=thread, body_html="post content")
    assert post.name == thread.name

    post.thread = thread2
    assert post.name == thread2.name


def test_task_process_email():
    """Test the process_email function."""

    marker = "_____Write above this line to post_____"

    message = get_email_message_from_file("reply.email")
    newpost = process(message, marker)[0]
    assert newpost

    message = get_email_message_from_file("reply_nocharset_specified.email")
    newpost = process(message, marker)[0]
    assert newpost

    message = get_email_message_from_file("reply_no_marker.email")
    with raises(LookupError):
        process(message, marker)

    # dubious check
    message = get_email_message_from_file("reply_no_textpart.email")
    with raises(LookupError):
        process(message, marker)
