# Copyright (c) 2012-2024, Abilian SAS

"""Configuration specific to integration tests.

Note: app is extranet.app
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import fixture

from abilian.sbe.app import create_app
from tests.conftest import TestConfig

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import TempPathFactory

    from abilian.app import Application

PUBLIC_ENDPOINTS = [
    "login.forgotten_pw_form",
    "login.login_form",
    # 'calendar.calendar_ics',
    # 'calendar.index',
    # 'home.public',
    # 'home.legal',
    # 'evenement_public.list_view',
    # 'debug.index',
    # 'calendar.events_feed',
    # 'api.adherents',
    # 'api.amis',
    # 'api.calendar',
    # 'api.manifestations',
    # 'api.projets',
]

ENDPOINTS_TO_IGNORE = {
    "login.logout",  # would end the session the sweep runs in
}


@fixture(scope="module")
def instance_path(tmp_path_factory: TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("instance")
    for name in ("tmp", "cache", "data"):
        (path / name).mkdir()
    return path


@fixture(scope="module")
def app(instance_path: Path) -> Application:
    return create_app(config=TestConfig, instance_path=str(instance_path))
