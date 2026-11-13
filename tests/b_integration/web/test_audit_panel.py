# Copyright (c) 2012-2024, Abilian SAS

"""Rendering an audit entry that has no actor.

Both `AuditEntry.user_id` and `SecurityAudit.manager_id` are nullable, because
anything done outside a request -- a migration, `flask createuser`,
`create_root_user` -- is recorded with nobody who did it. Two of the three
places that rendered an actor assumed there was one, and took the whole admin
audit panel down with an AttributeError on the first such entry.

The panel test in tests/c_e2e/web/test_admin_views.py covers this too, but only
by accident of a fixture granting a role outside a login. These are the direct
assertions.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from abilian.web.admin.panels.audit import BaseEntryPresenter
from abilian.web.views.images import user_url_args

if TYPE_CHECKING:
    from abilian.app import Application


def test_a_null_actor_renders_as_the_system(app: Application) -> None:
    presenter = BaseEntryPresenter(None, datetime(2026, 1, 1, 12, 0))

    with app.test_request_context("/"):
        rendered = presenter.render_user(None)

    assert "System" in rendered
    assert "<a" not in rendered, "there is no user page to link to"


def test_a_real_actor_still_gets_a_link(app: Application, user) -> None:
    presenter = BaseEntryPresenter(user, datetime(2026, 1, 1, 12, 0))

    with app.test_request_context("/"):
        rendered = presenter.render_user(user)

    assert f"user_id={user.id}" in rendered or f"/{user.id}" in rendered
    assert user.name in rendered


def test_a_null_actor_gets_the_default_avatar(app: Application) -> None:
    """The avatar helper is the other half: it dereferenced the user too."""
    with app.test_request_context("/"):
        endpoint, kwargs = user_url_args(None, 16)

    assert endpoint == "images.user_default"
    assert "user_id" not in kwargs
