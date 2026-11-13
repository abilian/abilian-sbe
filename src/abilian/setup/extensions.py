# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import defusedxml
import sqlalchemy as sa
import sqlalchemy.exc
from flask import current_app, url_for
from flask_migrate import Migrate
from loguru import logger
from markupsafe import Markup

import abilian.core.util
import abilian.i18n
from abilian.core import extensions
from abilian.extensions import vite
from abilian.services import (
    activity_service,
    antivirus,
    audit_service,
    auth_service,
    blob_store,
    conversion_service,
    index_service,
    preferences_service,
    security_service,
    session_blob_store,
    vocabularies_service,
)
from abilian.services.security import is_site_admin
from abilian.web import csrf
from abilian.web.action import actions
from abilian.web.admin import Admin

if TYPE_CHECKING:
    from flask import Flask

defusedxml.defuse_stdlib()

db = extensions.db

#: Vite dev server, used only when the app runs in debug mode.
#: Must match `server.port` in vite/vite.config.js, which pins it with
#: strictPort. Override with FLASK_VITE_DEV_SERVER if the port is taken.
VITE_DEV_SERVER = "http://localhost:5180"


def vite_asset(path: str) -> Markup:
    """Render the tag loading a Vite-built asset.

    In debug mode the asset is served by the Vite dev server. Otherwise it comes
    from the build output shipped inside the package, which `make front` writes
    to `abilian/sbe/static/vite/` and `abilian_sbe_static` serves.
    """
    filename = path.rsplit("/", 1)[-1]

    if current_app.debug:
        base = current_app.config.get("VITE_DEV_SERVER", VITE_DEV_SERVER)
        url = f"{base}/{path}"
        if filename.endswith(".css"):
            # The dev server hands CSS back as a JS module, because that is how
            # it drives HMR -- and a browser refuses that MIME type for
            # <link rel="stylesheet">, leaving the page unstyled. `?direct`
            # asks Vite for the plain text/css bytes instead.
            url += "?direct"
    else:
        url = url_for("abilian_sbe_static", filename=f"vite/{filename}")

    if filename.endswith(".css"):
        return Markup(f'<link rel="stylesheet" href="{url}" />')
    if filename.endswith(".js"):
        return Markup(f'<script type="module" src="{url}"></script>')

    msg = f"Don't know how to load Vite asset {path!r}: expected .css or .js"
    raise ValueError(msg)


# Silence those warnings for now.
warnings.simplefilter("ignore", category=sa.exc.SAWarning)


def init_extensions(app: Flask) -> None:
    """Initialize flask extensions, helpers and services."""

    extensions.redis.init_app(app)
    extensions.mail.init_app(app)
    extensions.upstream_info.extension.init_app(app)

    actions.init_app(app)

    # auth_service installs a `before_request` handler (actually, it's
    # flask-login). We want to authenticate the user ASAP, so that sentry and
    # logs can report which user encountered any error happening later,
    # in particular in a before_request handler (like csrf validator)
    auth_service.init_app(app)

    vite.init_app(app)
    app.jinja_env.globals["vite_asset"] = vite_asset
    # Templates ask the question by name. They used to read `g.is_manager`,
    # which two producers wrote with two different meanings.
    app.jinja_env.globals["is_site_admin"] = is_site_admin

    # Initialize legacy assets for favicons and other static resources
    from abilian.web import assets as legacy_assets

    legacy_assets.init_app(app)

    init_babel(app)

    init_csrf(app)

    # Flask-Migrate
    Migrate(app, db)

    # Abilian Core services
    security_service.init_app(app)
    blob_store.init_app(app)
    session_blob_store.init_app(app)
    audit_service.init_app(app)
    index_service.init_app(app)
    activity_service.init_app(app)
    preferences_service.init_app(app)
    conversion_service.init_app(app)
    vocabularies_service.init_app(app)
    antivirus.init_app(app)

    # Admin interface
    Admin().init_app(app)


def init_babel(app: Flask) -> None:
    # Babel (for i18n)
    babel = abilian.i18n.babel
    # Temporary (?) workaround
    babel.locale_selector_func = None
    babel.timezone_selector_func = None

    babel.init_app(app)

    babel.add_translations("wtforms", translations_dir="locale", domain="wtforms")
    babel.add_translations("abilian")


def init_csrf(app: Flask) -> None:
    # CSRF by default
    if app.config.get("WTF_CSRF_ENABLED"):
        # extensions.csrf IS original wtf_csrf
        # abilian_csrf is
        # from .csrf import abilian_csrf
        # from .csrf import wtf_csrf as csrf

        extensions.csrf.init_app(app)  # double initialization
        app.extensions["csrf"] = extensions.csrf
        extensions.abilian_csrf.init_app(app)

    app.register_blueprint(csrf.csrf_blueprint)


def init_sentry(app: Flask) -> None:
    """Install Sentry handler if config defines 'SENTRY_DSN'."""
    dsn = app.config.get("SENTRY_DSN")
    if not dsn:
        return

    try:
        import sentry_sdk
    except ImportError:
        logger.error(
            'SENTRY_DSN is defined in config but package "sentry-sdk" is not installed.'
        )
        return

    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FlaskIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
    )
