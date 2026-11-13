# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import Any

from flask import Flask
from werkzeug.datastructures import ImmutableDict

from abilian.web.action import Endpoint


class DefaultConfig:
    # Seriously: this needs to be changed in production
    SECRET_KEY = "CHANGEME"  # noqa: S105

    # Need to be explicitly defined in production configs
    PRODUCTION = False

    # Security (see
    # https://blog.miguelgrinberg.com/post/cookie-security-for-flask-applications)
    # NB: SESSION_COOKIE_* are now set up by Talisman
    WTF_CSRF_ENABLED = True

    # Babel
    BABEL_ACCEPT_LANGUAGES = ["en"]
    DEFAULT_COUNTRY = None

    # Shown in the page title, the logo alt text and the login heading.
    SITE_NAME = "Abilian SBE"

    # Static assets are served with a far-future expiry: every static URL is
    # stamped with the file's mtime (see `stamp_static_version`), so a changed
    # file gets a new URL. Without this Flask sends `no-cache` and the browser
    # revalidates all ~35 assets on every single page view.
    STATIC_CACHE_MAX_AGE = 31536000

    # Sentry
    SENTRY_SDK_URL = "https://browser.sentry-cdn.com/4.5.3/bundle.min.js"

    # Talisman's HTTPS redirect. Deployments that terminate TLS at a proxy, and
    # local runs with debug off, need it off; Talisman still honours
    # X-Forwarded-Proto when it is on.
    TALISMAN_FORCE_HTTPS = True

    # Content Security Policy, applied by Talisman whenever debug is off.
    #
    # No inline scripts and no inline event handlers: a template that needs to
    # hand something to a script does it with data attributes or a
    # <script type="application/json"> block. TRACKING_CODE goes through this as
    # well, so it has to load its script by URL, from an allowed origin.
    CONTENT_SECURITY_POLICY = {
        "default-src": "'self'",
        "script-src": "'self' https://browser.sentry-cdn.com",
        "style-src": "'self' 'unsafe-inline'",
        # blob: is the image widget's preview of a file not yet uploaded. Only
        # the page's own scripts can mint a blob: URL.
        "img-src": "'self' data: blob:",
        "object-src": "'none'",
    }

    # SQLAlchemy
    SQLALCHEMY_POOL_RECYCLE = 1800  # 30min. default value in flask_sa is None
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Debug settings (override default)
    DEBUG_TB_INTERCEPT_REDIRECTS = False

    # Abilian-specific
    PRIVATE_SITE = False
    PLUGINS = ()
    ADMIN_PANELS = (
        "abilian.web.admin.panels.dashboard.DashboardPanel",
        "abilian.web.admin.panels.audit.AuditPanel",
        "abilian.web.admin.panels.login_sessions.LoginSessionsPanel",
        "abilian.web.admin.panels.settings.SettingsPanel",
        "abilian.web.admin.panels.users.UsersPanel",
        "abilian.web.admin.panels.groups.GroupsPanel",
        "abilian.web.admin.panels.sysinfo.SysinfoPanel",
        "abilian.web.admin.panels.impersonate.ImpersonatePanel",
        "abilian.services.vocabularies.admin.VocabularyPanel",
        "abilian.web.tags.admin.TagPanel",
    )
    LOGO_URL = Endpoint("abilian_static", filename="img/logo-abilian-32x32.png")
    ABILIAN_UPSTREAM_INFO_ENABLED = False  # upstream info extension
    TRACKING_CODE = ""  # tracking code for web analytics to insert before </body>
    MAIL_ADDRESS_TAG_CHAR = None

    DRAMATIQ_BROKER = "dramatiq.brokers.redis:RedisBroker"


default_config: dict[str, Any] = dict(Flask.default_config)
default_config.update(vars(DefaultConfig))
default_config = ImmutableDict(default_config)
