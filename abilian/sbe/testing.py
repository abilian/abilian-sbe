from abilian import testing

from .app import Application


class TestConfig(testing.TestConfig):
    CELERY_ALWAYS_EAGER = True  # run tasks locally, no async
    CELERY_EAGER_PROPAGATES_EXCEPTIONS = True


class BaseTestCase(testing.BaseTestCase):
    application_class = Application
    config_class = TestConfig

    def get_setup_config(self):
        """ Called before creating application class
    """
        config = testing.BaseTestCase.get_setup_config(self)
        if hasattr(self, 'no_login'):
            config.NO_LOGIN = self.no_login

        return config
