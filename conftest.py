"""Configuration and injectable fixtures for Pytest.

Reuses fixtures defined in abilian-core.
"""
import logging
import os

from pytest import fixture

from abilian.sbe.app import create_app
from abilian.testing.fixtures import TestConfig

pytest_plugins = [
    "abilian.testing.fixtures",
    "abilian.sbe.apps.communities.tests.fixtures",
]


if os.environ.get("COLLECT_ANNOTATIONS"):

    def pytest_collection_finish(session):
        """Handle the pytest collection finish hook: configure pyannotate.
        Explicitly delay importing `collect_types` until all tests have
        been collected.  This gives gevent a chance to monkey patch the
        world before importing pyannotate.
        """
        from pyannotate_runtime import collect_types

        collect_types.init_types_collection()

    @fixture(autouse=True)
    def collect_types_fixture():
        from pyannotate_runtime import collect_types

        collect_types.resume()
        yield
        collect_types.pause()

    def pytest_sessionfinish(session, exitstatus):
        from pyannotate_runtime import collect_types

        collect_types.dump_stats("type_info.json")


class NoCsrfTestConfig(TestConfig):
    WTF_CSRF_ENABLED = False


@fixture
def config():
    return NoCsrfTestConfig


@fixture
def app(config):
    """Return an App configured with config=TestConfig."""
    return create_app(config=config)


@fixture
def req_ctx(app, request_ctx):
    """Simple alias (TBR)"""
    return request_ctx
