# Copyright (c) 2012-2024, Abilian SAS

"""Configuration specific to integratin tests.

Note: app is extranet.app
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pytest import fixture

from abilian.sbe.app import create_app
from tests.conftest import TestConfig

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
def instance_path(tmpdir_factory):
    instance_path = str(tmpdir_factory.mktemp("instance"))
    tmp_dir = Path(instance_path)
    (tmp_dir / "tmp").mkdir()
    (tmp_dir / "cache").mkdir()
    (tmp_dir / "data").mkdir()

    yield instance_path

    shutil.rmtree(str(instance_path))


@fixture(scope="module")
def app(instance_path):
    return create_app(config=TestConfig)
