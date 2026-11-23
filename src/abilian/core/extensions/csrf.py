# Copyright (c) 2012-2024, Abilian SAS

"""CSRF protection: flask-wtf checks the token of every POST, before its view.

A request without a valid token is refused with a 400, which the app's error
page presents; the routes that take none (an unsubscribe link) are exempt.
"""

from __future__ import annotations

from flask_wtf.csrf import CSRFProtect

wtf_csrf = CSRFProtect()
