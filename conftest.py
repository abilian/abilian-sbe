# coding=utf-8
"""Configuration and injectable fixtures for Pytest.

Reuses fixtures defined in abilian-core.
"""
from abilian.testing.fixtures import TestConfig
from pytest import fixture

from abilian.sbe.app import create_app

pytest_plugins = [
    "abilian.testing.fixtures",
    "abilian.sbe.apps.communities.tests.fixtures",
]


class NoCsrfTestConfig(TestConfig):
    WTF_CSRF_ENABLED = False


@fixture
def config():
    return NoCsrfTestConfig


@fixture
def app(config):
    """Return an App configured with config=TestConfig."""
    return create_app(config=config)
