# coding=utf-8
"""
Notifications
"""
from __future__ import absolute_import

from abilian.sbe.extension import sbe

# Constants
TOKEN_SERIALIZER_NAME = "unsubscribe_sbe"


def register_plugin(app):
    cfg = app.config.setdefault('ABILIAN_SBE', {})
    cfg.setdefault('DAILY_SOCIAL_DIGEST_SUBJECT',
                   u'Des nouvelles de vos communautés')
    sbe.init_app(app)

    # TODO: Slightly confusing. Reorg?
    from .views import notifications, social  # noqa
    from .tasks.social import DIGEST_TASK_NAME, DEFAULT_DIGEST_SCHEDULE

    CELERYBEAT_SCHEDULE = app.config.setdefault('CELERYBEAT_SCHEDULE', {})

    if DIGEST_TASK_NAME not in CELERYBEAT_SCHEDULE:
        CELERYBEAT_SCHEDULE[DIGEST_TASK_NAME] = DEFAULT_DIGEST_SCHEDULE

    app.register_blueprint(notifications)
