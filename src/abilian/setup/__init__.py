# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from itertools import count
from typing import TYPE_CHECKING, Any

import jinja2
import sqlalchemy as sa
import sqlalchemy.orm
import svcs
from flask import Flask, appcontext_pushed, g, request_started
from flask_super import register_commands
from flask_talisman import DEFAULT_CSP_POLICY, Talisman

from abilian.core import extensions, signals

# Vite integration now handled by Flask-Vite in setup/extensions.py
from abilian.services import settings_service
from abilian.services.security import ANONYMOUS
from abilian.web.access_blueprint import allow_access_for_roles
from abilian.web.nav import setup_nav_and_breadcrumbs

from .blueprints import setup_blueprints
from .debug import setup_debug
from .extensions import init_extensions, init_sentry
from .logging import init_logging

if TYPE_CHECKING:
    from abilian.app import Application


def setup_app(app: Application, plugins=None) -> None:
    # At this point we have loaded all external config files:
    # SQLALCHEMY_DATABASE_URI is definitively fixed (it cannot be defined in
    # database AFAICT), and LOGGING_FILE cannot be set in DB settings.

    svcs.flask.init_app(app)

    init_logging(app)
    init_sentry(app)

    # time to load config bits from database: 'settings'
    # First init required stuff: db to make queries, and settings service
    extensions.db.init_app(app)
    settings_service.init_app(app)

    init_extensions(app)

    app.register_jinja_loaders(jinja2.PackageLoader("abilian.web"))

    app.install_default_handlers()

    if app.debug and not app.testing:
        setup_debug(app)

    if not app.debug:
        # CSP
        csp = app.config.get("CONTENT_SECURITY_POLICY", DEFAULT_CSP_POLICY)
        Talisman(
            app,
            content_security_policy=csp,
            force_https=app.config.get("TALISMAN_FORCE_HTTPS", True),
        )

    setup_blueprints(app)

    plugins = (plugins or []) + list(app.config["PLUGINS"])

    with app.app_context():
        app.plugin_manager.register_plugins(plugins)

    init_access_controllers(app)

    # Vite assets don't need finalization like Flask-Assets did

    # At this point all models should have been imported: time to configure
    # mappers. Normally Sqlalchemy does it when needed but mappers may be
    # configured inside sa.orm.class_mapper() which hides a
    # misconfiguration: if a mapper is misconfigured its exception is
    # swallowed by class_mapper(model) results in this laconic
    # (and misleading) message: "model is not mapped"
    sa.orm.configure_mappers()

    if not app.testing:
        with app.app_context():
            # Time to generate the JS API
            signals.register_js_api.send(app)

            # Initialize Abilian core services.
            # Must come after all entity classes have been declared.
            # Delegated to ServiceManager. Will need some configuration love
            # later.
            app.service_manager.start_services()

    connect_signals()

    # Register CLI commands
    register_commands(app)


def connect_signals() -> None:
    appcontext_pushed.connect(install_id_generator)
    request_started.connect(setup_nav_and_breadcrumbs)


# TODO: remove
def install_id_generator(sender: Flask, **kwargs: Any) -> None:
    g.id_generator = count(start=1)


def init_access_controllers(app: Application) -> None:
    app.add_access_controller(
        "static", allow_access_for_roles(ANONYMOUS), endpoint=True
    )
    # debugtoolbar: this is needed to have it when not authenticated
    # on a private site. We cannot do this in init_debug_toolbar,
    # since auth service is not yet installed.
    app.add_access_controller(
        "debugtoolbar",
        allow_access_for_roles(ANONYMOUS),
    )
    app.add_access_controller(
        "_debug_toolbar.static",
        allow_access_for_roles(ANONYMOUS),
        endpoint=True,
    )
