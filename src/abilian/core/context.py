# Copyright (c) 2012-2024, Abilian SAS

"""Where the framework keeps the acting principal.

This is the seam. Below the web layer, one module knows that the application
runs on Flask and that `g` and `flask_login` exist; everything else either takes
its subject as an argument or asks here. Swapping the framework is then this
file plus the view layer, rather than every place that happened to reach for a
global.

The reads collected here were each spelled differently at each call site, and
each swallowed a different set of failures:

- `OwnedMixin.__init__` did `g.user` inside `except (RuntimeError,
  AttributeError): pass`.
- `SecurityService._current_user_manager` did `g.user` inside
  `except Exception:` and fell back to `User.get(0)` -- which is `None` when the
  SYSTEM user has not been created, and that is how `SecurityAudit.manager`
  came to be null and take the admin audit panel down.
- `query_entity_with_permission` and `is_site_admin` used flask-login's
  `current_user` proxy instead, which is an anonymous user object rather than
  absent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import g, has_app_context

if TYPE_CHECKING:
    from abilian.core.models.subjects import User


def get_current_principal() -> User | None:
    """The user acting in this context, or None if nobody is.

    None is an answer, not a failure. A dramatiq task, a CLI command, a
    migration and `create_root_user` all run with no request and no user, and
    an anonymous visitor has none either -- a caller that needs to tell those
    apart should ask for what it actually needs, which is usually a permission.

    Reads `g.user`, which AuthService sets when flask-login loads a user, and
    deliberately does *not* fall back to flask-login's `current_user` proxy.
    Resolving that proxy makes flask-login load and then **cache** its result in
    `g._login_user`; `g` lives on the app context, so doing it while no real
    request is in flight caches an anonymous user that the next request inherits
    instead of loading from the session. The test harness pushes a request
    context, so this is not hypothetical -- an earlier version of this function
    logged every test user out.

    By the time a view or template can ask, `g.user` is set: AuthService's
    `do_access_control` before_request has already touched `current_user`.
    """
    if not has_app_context():
        return None
    return g.get("user")
