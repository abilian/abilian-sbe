# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from flask_login import current_user, login_user
from pytest import fixture

from abilian.app import Application, setup_app
from abilian.core.models.subjects import User
from abilian.services import get_service, security_service
from abilian.services.preferences.models import UserPreference
from abilian.services.preferences.panel import PreferencePanel
from abilian.services.preferences.service import PreferenceService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from abilian.core.sqlalchemy import SQLAlchemy
    from abilian.services.security import SecurityService


class VisiblePanel(PreferencePanel):
    id = label = "visible"

    def is_accessible(self) -> bool:
        return True

    def get(self) -> str:
        return "Visible"


class AdminPanel(PreferencePanel):
    id = label = "admin"

    def is_accessible(self) -> bool:
        security = cast("SecurityService", get_service("security"))
        return security.has_role(current_user, "admin")

    def get(self) -> str:
        return "Admin"


@fixture
def app(config: type) -> Application:
    app = Application()
    app.configure(config)
    setup_app(app)

    with app.app_context():
        prefs = cast("PreferenceService", get_service("preferences"))
        prefs.app_state.panels = []
        prefs.register_panel(VisiblePanel(), app)
        prefs.register_panel(AdminPanel(), app)

    return app


def test_preferences(app: Application, session: Session) -> None:
    user = User(email="test@example.com")
    assert UserPreference.query.all() == []

    preference_service = PreferenceService()

    preferences = preference_service.get_preferences(user)
    assert preferences == {}

    preference_service.set_preferences(user, digest="daily")
    session.flush()

    preferences = preference_service.get_preferences(user)
    assert preferences == {"digest": "daily"}

    preference_service.clear_preferences(user)
    session.flush()

    preferences = preference_service.get_preferences(user)
    assert preferences == {}
    assert UserPreference.query.all() == []


def test_preferences_with_various_types(app: Application, session: Session) -> None:
    user = User(email="test@example.com")
    preference_service = PreferenceService()

    preference_service.set_preferences(user, some_int=1)
    session.flush()
    preferences = preference_service.get_preferences(user)
    assert preferences == {"some_int": 1}

    preference_service.set_preferences(user, some_bool=True)
    session.flush()
    preferences = preference_service.get_preferences(user)
    assert preferences == {"some_int": 1, "some_bool": True}


@pytest.mark.skip("FIXME ASAP")
def test_visible_panels(app: Application, db: SQLAlchemy) -> None:
    user = User(email="test@example.com")

    with app.test_request_context():
        security_service.start()
        login_user(user)

        for cp in app.template_context_processors["preferences"]:
            ctx = cp()
            if "menu" in ctx:
                break

        expected = ["preferences.visible"]
        assert [p["endpoint"] for p in ctx["menu"]] == expected

        security_service.grant_role(user, "admin")
        ctx = cp()
        expected = ["preferences.visible", "preferences.admin"]
        assert [p["endpoint"] for p in ctx["menu"]] == expected
