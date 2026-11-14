# Copyright (c) 2012-2024, Abilian SAS

"""Base classes for file download."""

from __future__ import annotations

from datetime import datetime, timedelta

from flask import Response, request
from werkzeug.exceptions import BadRequest

from abilian.core.util import utc_dt

from .base import View


class BaseFileDownload(View):
    set_expire = False
    expire_offset = timedelta(days=365)
    as_attachment = False

    #: argument name that must be found in view kwargs. This is a safety measure
    #: to prevent setting far expire date on resources without a varying argument
    #: in url (path or query string), such as a timestamp, a serial, a hash...
    expire_vary_arg = None

    def __init__(
        self,
        set_expire=None,
        expire_offset=None,
        expire_vary_arg=None,
        as_attachment=None,
    ) -> None:
        # Override class default value only if arg is specified in constructor.
        # This allows subclasses to easily override these defaults.
        if set_expire is not None:
            self.set_expire = set_expire
        if expire_offset is not None:
            self.expire_offset = expire_offset
        if expire_vary_arg is not None:
            self.expire_vary_arg = expire_vary_arg
        if as_attachment is not None:
            self.as_attachment = bool(as_attachment)

        if self.set_expire:
            if not self.expire_offset:
                msg = "expire_offset is not set"
                raise ValueError(msg)
            if not self.expire_vary_arg:
                msg = "expire_vary_arg is not set"
                raise ValueError(msg)

    def prepare_args(self, args, kwargs):
        if self.set_expire:
            vary_arg = kwargs.get(
                self.expire_vary_arg, request.args.get(self.expire_vary_arg)
            )
            if vary_arg is None:
                # Argument for timestamp, serial etc is missing.
                # We must refuse to serve an image with expiry date set up
                # to maybe 1 year from now.
                # Check the code that has generated this url!
                msg = f"File version marker is missing ({self.expire_vary_arg!r}=?)"
                raise BadRequest(msg)

        args, kwargs = super().prepare_args(args, kwargs)
        kwargs["attach"] = request.args.get("attach", self.as_attachment, type=bool)
        return args, kwargs

    def make_response(self, *args, **kwargs) -> Response:
        # for example: return flask.make_response(...)
        # or: return flask.send_file(...)
        raise NotImplementedError

    def get_filename(self, *args, **kwargs) -> str:
        raise NotImplementedError

    def get_content_type(self, *args, **kwargs) -> str:
        raise NotImplementedError

    def get(self, attach: bool, *args, **kwargs):
        """
        :param attach: if True, return file as an attachment.
        """
        response: Response = self.make_response(*args, **kwargs)
        response.content_type = self.get_content_type(*args, **kwargs)

        if attach:
            filename = self.get_filename(*args, **kwargs)
            if not filename:
                filename = "file.bin"
            headers = response.headers
            headers.add("Content-Disposition", "attachment", filename=filename)

        self.set_cache_headers(response)
        return response

    def set_cache_headers(self, response) -> None:
        if self.set_expire:
            response.cache_control.public = False
            response.cache_control.private = True
            response.cache_control.max_age = int(self.expire_offset.total_seconds())
            response.expires = utc_dt(datetime.utcnow() + self.expire_offset)
