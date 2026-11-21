# Copyright (c) 2012-2024, Abilian SAS

"""`/health` answers whoever asks, over plain HTTP.

A platform checks it on the app's own port, without signing in and without the
proxy that makes a request HTTPS: on a private site in production, every other
page sends that request away, to the sign-in page or to HTTPS.
"""

from __future__ import annotations

from abilian.sbe.app import create_app
from abilian.testing.conftest import TestConfig


class ProductionConfig(TestConfig):
    """A private site as it runs in production, HTTPS forced."""

    DEBUG = False
    PRIVATE_SITE = True


def test_health_answers_over_plain_http_without_signing_in() -> None:
    client = create_app(config=ProductionConfig).test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.text == "OK"


def test_the_other_pages_still_go_to_https() -> None:
    client = create_app(config=ProductionConfig).test_client()

    response = client.get("/user/login")

    assert response.status_code == 302
    assert response.location.startswith("https://")
