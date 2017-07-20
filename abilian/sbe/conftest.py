# coding=utf-8
"""
Configuration and injectable fixtures for Pytest.

Supposed to replace the too-complex current UnitTest-based testing
framework.

DI and functions over complex inheritance hierarchies FTW!
"""
from __future__ import absolute_import, division, print_function, \
    unicode_literals

from pytest import fixture, yield_fixture

from abilian.sbe.app import create_app
from abilian.services import get_service


class TestConfig:
    TESTING = True
    SERVER_NAME = 'localhost'
    # CSRF_ENABLED = False


@fixture(scope='session')
def app():
    """We usually only create an app once per session."""
    _app = create_app(config=TestConfig)
    return _app


@yield_fixture
def db(app):
    """Return a fresh db for each test."""
    from abilian.core.extensions import db

    with app.app_context():
        stop_all_services(app)
        ensure_services_started(['repository', 'session_repository'])

        cleanup_db(db)
        db.create_all()
        yield db

        db.session.remove()
        cleanup_db(db)
        stop_all_services(app)


@fixture
def client(app, db):
    """Return a Web client, used for testing, bound to a DB session."""
    return app.test_client()


#
# Cleanup utilities
#
def cleanup_db(db):
    """Drop all the tables, in a way that doesn't raise integrity errors."""

    # Need to run this sequence twice for some reason
    for i in range(0, 2):
        for table in reversed(db.metadata.sorted_tables):
            try:
                db.session.execute(table.delete())
            except:
                pass
    # Just in case ?
    db.drop_all()


def stop_all_services(app):
    for service in app.services.values():
        if service.running:
            service.stop()


def ensure_services_started(services):
    for service_name in services:
        service = get_service(service_name)
        if not service.running:
            service.start()
