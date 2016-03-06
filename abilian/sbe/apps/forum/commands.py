# coding=utf-8
"""

"""
from __future__ import absolute_import

import fileinput
import logging
import sys
from email.parser import FeedParser

from flask_script import Manager

from .tasks import check_maildir, process_email

logger = logging.getLogger(__name__)

manager = Manager(description='SBE forum commands', help='SBE forum commands')


@manager.option('-f',
                '--filename',
                help='email filename; defaults to standard input',
                default=u'-',
                required=False,)
def inject_email(filename=u'-'):
    """Read one email from stdin, parse it, forward it in a celery task to be persisted."""

    parser = FeedParser()

    if logger.level is logging.NOTSET:
        logger.setLevel(logging.INFO)

    try:
        # iterate over stdin
        for line in fileinput.input(filename):
            parser.feed(line)
    except KeyboardInterrupt:
        logger.info('Aborted by user, exiting.')
        sys.exit(1)
    except:
        logger.error('Error during email parsing', exc_info=True)
        sys.exit(1)
    finally:
        # close the parser to generate a email.message
        message = parser.close()
        fileinput.close()

    if message:
        # make sure no email.errors are present
        if not message.defects:
            process_email.delay(message)
        else:
            logger.error('email has defects, message content:\n'
                         '------ START -------\n'
                         '%s'
                         '\n------ END -------\n',
                         message,
                         extra={'stack': True,})
    else:
        logger.error('no email was parsed from stdin', extra={'stack': True,})


@manager.command
def check_email():
    """
    Read one email from current user Maildir, parse it, forward it in a celery task to be persisted.
    """

    # FIXME: doesn't appear legit.
    check_maildir.delay()
