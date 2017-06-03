# coding=utf-8
"""
"""
from __future__ import absolute_import, division, print_function, \
    unicode_literals

from pytest import fixture, yield_fixture

from abilian.sbe import create_app
from abilian.services import get_service


class TestConfig:
    TESTING = True
    SERVER_NAME = 'localhost'
    # CSRF_ENABLED = False


@fixture(scope='session')
def app():
    _app = create_app(config=TestConfig)
    return _app


# XXX: not sure we really need both 'db' and 'db_session' ???
@yield_fixture(scope="session")
def db(app):
    """
    Creates clean database schema and drops it on teardown.

    Note, that this is a session scoped fixture, it will be executed only once
    and shared among all tests. Use `db` fixture to get clean database before
    each test.
    """
    from abilian.core.extensions import db

    with app.app_context():
        db.create_all()
        yield db

        db.session.remove()
        cleanup_db(db)
        # Is this needed ?
        # db.session.bind.dispose()


@yield_fixture(scope="function")
def db_session(db, app):
    with app.app_context():
        stop_all_services(app)
        ensure_services_started(['repository', 'session_repository'])

        cleanup_db(db)
        db.create_all()
        yield db.session

        db.session.remove()
        cleanup_db(db)
        stop_all_services(app)


@fixture(scope='function')
def client(app, db_session):
    return app.test_client()


#
# Cleanup utilities
#
def cleanup_db(db):
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
