# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals

from abilian.testing import BaseTestCase as BaseBaseTestCase
from abilian.testing import TestConfig

from .app import Application


class BaseTestCase(BaseBaseTestCase):
    application_class = Application
    config_class = TestConfig

    def get_setup_config(self):
        """Called before creating application class."""
        config = BaseBaseTestCase.get_setup_config(self)
        if hasattr(self, "no_login"):
            config.NO_LOGIN = self.no_login

        return config
