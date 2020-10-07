import email
import mailbox

from abilian.core.util import unwrap
from flask import current_app

from abilian.sbe.apps.forum.tasks import (
    has_subtag,
    extract_email_destination,
    MAIL_REPLY_MARKER,
    process,
)

maildirpath = "./test-data/Maildir"


def process_email(message: email.message.Message) -> bool:
    """Email.Message object from command line script Run message (parsed
    email).

    Processing chain extract community thread post member from reply_to
    persist post in db.
    """
    app = unwrap(current_app)
    # Extract post destination from To: field, (community/forum/thread/member)
    to_address = message["To"]

    assert isinstance(to_address, str)
    print(to_address)

    if not (has_subtag(to_address)):
        print(f"Email {to_address!r} has no subtag, skipping...")
        return False

    try:
        infos = extract_email_destination(to_address)
        print(infos)
        locale = infos[0]
        # thread_id = infos[1]
        # user_id = infos[2]
    except BaseException:
        print(
            f"Recipient {to_address!r} cannot be converted to locale/thread_id/user.id"
        )
        return False

    # Translate marker with locale from email address
    rq_headers = [("Accept-Language", locale)]
    with app.test_request_context("/process_email", headers=rq_headers):
        marker = str(MAIL_REPLY_MARKER)

    # Extract text and attachments from message
    try:
        newpost, attachments = process(message, marker)
        print(newpost, attachments)
    except BaseException:
        print("Could not Process message")


def check_maildir():
    """Check the MailDir for emails to be injected in Threads.

    This task is registered only if `INCOMING_MAIL_USE_MAILDIR` is True.
    By default it is run every minute.
    """
    incoming_mailbox = mailbox.Maildir(maildirpath)
    incoming_mailbox.lock()  # Useless but recommended if old mbox is used by error

    for key, message in incoming_mailbox.items():
        print(key)
        process_email(message)
        print()


check_maildir()
