# coding=utf-8
"""Configuration and injectable fixtures for Pytest.

Reuses fixtures defined in abilian-core.
"""
from __future__ import absolute_import, division, print_function, \
    unicode_literals

from abilian.testing.fixtures import TestConfig
from pytest import fixture

from abilian.sbe.app import create_app

pytest_plugins = ["abilian.testing.fixtures"]


class NoCsrfTestConfig(TestConfig):
    WTF_CSRF_ENABLED = False
    CSRF_ENABLED = False
    # SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@fixture
def config():
    return NoCsrfTestConfig


@fixture
def app(config):
    """Return an App configured with config=TestConfig."""
    assert config.CSRF_ENABLED == False
    assert config.WTF_CSRF_ENABLED == False
    return create_app(config=config)
