# coding=utf-8
"""Configuration and injectable fixtures for Pytest.

Supposed to replace the too-complex current UnitTest-based testing
framework.

DI and functions over complex inheritance hierarchies FTW!
"""
from __future__ import absolute_import, division, print_function, \
    unicode_literals

from pytest import fixture

from abilian.sbe.app import create_app

pytest_plugins = ['abilian.testing.fixtures']


@fixture
def app(config):
    """Return an App configured with config=TestConfig."""
    return create_app(config=config)


# class TestConfig:
#     TESTING = True
#     SERVER_NAME = 'localhost'
#     CELERY_ALWAYS_EAGER = True  # run tasks locally, no async
#     CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
#     MAIL_SENDER = 'tester@example.com'
#     SITE_NAME = "Abilian Test"
#     CSRF_ENABLED = True
#     WTF_CSRF_ENABLED = True
#     BABEL_ACCEPT_LANGUAGES = ['en', 'fr']

#
# # Change to True to enable errors on warnings
# if True:
#     import warnings
#     # Do not remove !
#     import pandas
#     from sqlalchemy.exc import SADeprecationWarning
#     warnings.simplefilter("ignore", SADeprecationWarning)
#     warnings.simplefilter("ignore", FutureWarning)
#     warnings.simplefilter("ignore", DeprecationWarning)
#     # warnings.simplefilter("error")
#
#
# @fixture
# def config():
#     return TestConfig
#
#
# @fixture
# def app(config):
#     """Return an App configured with config=TestConfig."""
#     return create_app(config=config)
#
#
# @fixture
# def db(app):
#     """Return a fresh db for each test."""
#     from abilian.core.extensions import db
#
#     with app.app_context():
#         stop_all_services(app)
#         ensure_services_started(['repository', 'session_repository'])
#
#         cleanup_db(db)
#         db.create_all()
#         yield db
#
#         db.session.remove()
#         cleanup_db(db)
#         stop_all_services(app)
#
#
# @fixture
# def session(db):
#     return db.session
#
#
# @fixture
# def app_context(app):
#     with app.app_context() as ctx:
#         yield ctx
#
#
# @fixture
# def test_request_context(app):
#     with app.test_request_context() as ctx:
#         yield ctx
#
#
# @fixture
# def client(app, db):
#     """Return a Web client, used for testing, bound to a DB session."""
#     return app.test_client()
