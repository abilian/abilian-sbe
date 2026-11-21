# Copyright (c) 2012-2024, Abilian SAS

"""The Maildir is checked only on a site that receives replies there.

Scheduled on every site, the check fails each minute where there is no Maildir,
which is everywhere else.
"""

from __future__ import annotations

from abilian.core.dramatiq.scheduler import Job, crontab_from_config
from abilian.sbe.app import create_app
from abilian.sbe.apps.forum.tasks import check_maildir
from abilian.testing.conftest import TestConfig

MAILDIR_JOB = Job(actor=check_maildir, key="SCHEDULE_CHECK_MAILDIR")


class MaildirConfig(TestConfig):
    INCOMING_MAIL_USE_MAILDIR = True


def test_the_maildir_is_not_checked_by_default() -> None:
    app = create_app(config=TestConfig)

    assert crontab_from_config(app.config, MAILDIR_JOB) == ""


def test_the_maildir_is_checked_every_minute_when_it_is_used() -> None:
    app = create_app(config=MaildirConfig)

    assert crontab_from_config(app.config, MAILDIR_JOB) == "* * * * *"
