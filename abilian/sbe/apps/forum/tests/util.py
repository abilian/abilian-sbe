from email.feedparser import FeedParser
from pathlib import Path


def get_string_from_file(filename="notification.email"):
    """Load a test email, return as string."""
    filepath = Path(__file__).parent / "data" / filename
    with filepath.open("rt", encoding="utf-8") as email_file:
        email_string = email_file.read()
    return email_string


def get_email_message_from_file(filename="notification.email"):
    """Load a mail and parse it into a email.message."""
    email_string = get_string_from_file(filename)
    parser = FeedParser()
    parser.feed(email_string)
    email_message = parser.close()
    return email_message
