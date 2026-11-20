# Copyright (c) 2012-2024, Abilian SAS

"""An audit entry that has no actor.

Both `AuditEntry.user_id` and `SecurityAudit.manager_id` are nullable, because
anything done outside a request -- a migration, `flask createuser`,
`create_root_user` -- is recorded with nobody who did it. The log's page says
"The system" for them (`admin/_ads_macros.html`); the avatar helper must not
dereference the missing user either.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from abilian.web.views.images import user_url_args

if TYPE_CHECKING:
    from abilian.app import Application


def test_a_null_actor_gets_the_default_avatar(app: Application) -> None:
    """The avatar helper is the other half: it dereferenced the user too."""
    with app.test_request_context("/"):
        endpoint, kwargs = user_url_args(None, 16)

    assert endpoint == "images.user_default"
    assert "user_id" not in kwargs
