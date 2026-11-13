# Copyright (c) 2012-2024, Abilian SAS

"""The running application, typed as the class it always is here."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from flask.sansio.app import App

    from abilian.app import Application


def as_application(app: App) -> Application:
    """`app` typed as our `Application`.

    Flask hands the application over typed as its own base class: through
    `current_app`, or as `state.app` in a blueprint's setup callbacks. In this
    code base it is always an `Application`, which adds `default_view`,
    `service_manager`, `add_access_controller` and the like.
    """
    return cast("Application", app)
