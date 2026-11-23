# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, current_app
from flask_wtf import FlaskForm

if TYPE_CHECKING:
    from wtforms.csrf.core import CSRFTokenField

csrf_blueprint = Blueprint("csrf", __name__, url_prefix="/csrf")


@csrf_blueprint.route("/token", endpoint="json_token")
def json_token_view():
    return {"token": token()}


def field() -> CSRFTokenField | None:
    """Return an instance of `wtforms.ext.csrf.fields.CSRFTokenField`, suitable
    for rendering.

    Renders an empty string if `config.WTF_CSRF_ENABLED` is not set.
    """
    if current_app.config.get("WTF_CSRF_ENABLED"):
        form = FlaskForm()
        return form.csrf_token
    return None


def time_limit():
    """Return current time limit for CSRF token."""
    return current_app.config.get("WTF_CSRF_TIME_LIMIT", 3600)


def name() -> str:
    """Field name expected to have CSRF token.

    Useful for passing it to JavaScript for instance.
    """
    return "csrf_token"


def token() -> str:
    """Value of current csrf token.

    Useful for passing it to JavaScript for instance.
    """
    csrf_token = field()
    if csrf_token is None:
        return ""
    # csrf_token is a CSRFTokenField
    # csrf_token.current_token is the current token str content
    return csrf_token.current_token
