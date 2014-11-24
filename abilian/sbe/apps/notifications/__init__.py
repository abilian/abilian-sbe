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
  from .views import notifications, social
  from .tasks import social

  app.register_blueprint(notifications)
