# Copyright (c) 2012-2024, Abilian SAS

"""Base Flask application class, used by tests or to be extended in real
applications."""

from __future__ import annotations

from functools import partial

import sqlalchemy as sa
from flask import Flask, g, render_template
from flask.globals import request_ctx

from abilian.core import extensions

db = extensions.db


class ErrorManagerMixin(Flask):
    def setup_logging(self) -> None:
        # Force flask to create application logger before logging
        # configuration; else, flask will overwrite our settings
        assert self.logger

    def handle_user_exception(self, e):
        # Outside a nested transaction, the exception may have occured in
        # after_commit(): doing a rollback() raises an error and would hide
        # actual error.
        session = db.session()
        if session.is_active and session.in_nested_transaction():
            # Inconditionally forget all DB changes, and ensure clean session
            # during exception handling.
            session.rollback()
        else:
            self._remove_session_save_objects()

        return super().handle_user_exception(e)

    def handle_exception(self, e):
        session = db.session()
        if not session.is_active:
            # Something happened in error handlers and session is not usable
            # anymore.
            self._remove_session_save_objects()

        return super().handle_exception(e)

    def _remove_session_save_objects(self) -> None:
        """Used during exception handling in case we need to remove() session:

        keep instances and merge them in the new session.
        """
        if self.testing:
            return
        # Before destroying the session, get all instances to be attached to the
        # new session. Without this, we get DetachedInstance errors, like when
        # tryin to get user's attribute in the error page...
        old_session = db.session()
        g_objs = []
        for key in iter(g):
            obj = getattr(g, key)
            if isinstance(obj, db.Model) and sa.orm.object_session(obj) in (
                None,
                old_session,
            ):
                g_objs.append((key, obj, obj in old_session.dirty))

        db.session.remove()
        session = db.session()

        for key, obj, load in g_objs:
            # replace obj instance in bad session by new instance in fresh
            # session
            setattr(g, key, session.merge(obj, load=load))

        # refresh `current_user`
        user = getattr(request_ctx, "user", None)
        if user is not None and isinstance(user, db.Model):
            request_ctx.user = session.merge(user, load=load)

    def log_exception(self, exc_info) -> None:
        """Log exception only if Sentry is not used (this avoids getting error
        twice in Sentry)."""
        dsn = self.config.get("SENTRY_DSN")
        if not dsn:
            super().log_exception(exc_info)

    def install_default_handlers(self) -> None:
        for http_error_code in (403, 404, 500):
            self.install_default_handler(http_error_code)

    def install_default_handler(self, http_error_code: int) -> None:
        """Install a default error handler for `http_error_code`.

        The default error handler renders a template named error404.html
        for http_error_code 404.
        """
        # logger.debug(
        #     "Set Default HTTP error handler for status code {http_error_code}",
        #     http_error_code=http_error_code,
        # )
        handler = partial(self.handle_http_error, http_error_code)
        self.errorhandler(http_error_code)(handler)

    def handle_http_error(self, code, error):
        """Helper that renders `error{code}.html`.

        Convenient way to use it::

           from functools import partial
           handler = partial(app.handle_http_error, code)
           app.errorhandler(code)(handler)
        """
        # 5xx code: error on server side
        if (code // 100) == 5:
            # ensure rollback if needed, else error page may
            # have an error, too, resulting in raw 500 page :-(
            db.session.rollback()

        template = f"error{code:d}.html"
        return render_template(template, error=error), code
