# Copyright (c) 2012-2024, Abilian SAS

"""The Content Security Policy lets the browser report to Sentry, when it does."""

from __future__ import annotations

from abilian.setup import content_security_policy

POLICY = {"default-src": "'self'", "object-src": "'none'"}
SDK = "https://browser.sentry-cdn.com/4.5.3/bundle.min.js"
DSN = "https://0123abcd@o42.ingest.sentry.io/7"


def test_without_sentry_the_policy_is_as_configured() -> None:
    config = {"CONTENT_SECURITY_POLICY": POLICY}
    assert content_security_policy(config) == POLICY


def test_the_dsn_host_is_allowed_for_the_reports_and_nothing_else() -> None:
    config = {
        "CONTENT_SECURITY_POLICY": POLICY,
        "SENTRY_DSN": DSN,
        "SENTRY_SDK_URL": SDK,
    }

    policy = content_security_policy(config)

    assert policy["connect-src"] == "'self' https://o42.ingest.sentry.io"
    assert policy["default-src"] == "'self'"


def test_the_configured_policy_is_left_alone() -> None:
    config = {
        "CONTENT_SECURITY_POLICY": POLICY,
        "SENTRY_DSN": DSN,
        "SENTRY_SDK_URL": SDK,
    }
    content_security_policy(config)
    assert "connect-src" not in POLICY


def test_no_browser_sdk_no_browser_reports() -> None:
    """The template loads the SDK only when both are set."""
    config = {
        "CONTENT_SECURITY_POLICY": POLICY,
        "SENTRY_DSN": DSN,
        "SENTRY_SDK_URL": "",
    }
    assert "connect-src" not in content_security_policy(config)
