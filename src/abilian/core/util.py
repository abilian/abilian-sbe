# Copyright (c) 2012-2024, Abilian SAS

"""Various tools that don't belong some place specific."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import unicodedata
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Any

import pytz
from babel.dates import LOCALTZ
from flask import request
from werkzeug.local import LocalProxy


def unwrap(obj: Any):
    """Unwrap obj from werkzeug.local.LocalProxy if needed.

    This is required if one want to test `isinstance(obj, SomeClass)`.
    """
    if isinstance(obj, LocalProxy):
        obj = obj._get_current_object()
    return obj


def fqcn(cls: type) -> str:
    """Fully Qualified Class Name."""
    return str(f"{cls.__module__}.{cls.__name__}")


def friendly_fqcn(cls_or_cls_name: type | str) -> str:
    """Friendly name of fully qualified class name.

    :param cls_or_cls_name: a string or a class
    """
    if isinstance(cls_or_cls_name, type):
        cls_name = fqcn(cls_or_cls_name)
    else:
        cls_name = cls_or_cls_name

    return cls_name.rsplit(".", 1)[-1]


def utcnow() -> datetime:
    """Return a new aware datetime with current date and time, in UTC TZ."""
    return datetime.now(pytz.utc)


def local_dt(dt: datetime) -> datetime:
    """Return an aware datetime in system timezone, from a naive or aware
    datetime.

    Naive datetime are assumed to be in UTC TZ.
    """
    if not dt.tzinfo:
        dt = pytz.utc.localize(dt)
    return LOCALTZ.normalize(dt.astimezone(LOCALTZ))


def utc_dt(dt: datetime) -> datetime:
    """Set UTC timezone on a datetime object.

    A naive datetime is assumed to be in UTC TZ.
    """
    if not dt.tzinfo:
        return pytz.utc.localize(dt)
    return dt.astimezone(pytz.utc)


def get_params(names):
    """Return a dictionary with params from request.

    TODO: I think we don't use it anymore and it should be removed
    before someone gets hurt.
    """
    params = {}
    for name in names:
        value = request.form.get(name) or request.files.get(name)
        if value is not None:
            params[name] = value
    return params


def atomic_write(path: Path, data: bytes) -> None:
    """Write `data` to `path` so that no reader ever sees a partial file.

    Writes a temporary file beside `path`, then renames it over `path`.
    """
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


# From http://flask.pocoo.org/snippets/44/
class Pagination:
    def __init__(self, page, per_page, total_count) -> None:
        self.page = page
        self.per_page = per_page
        self.total_count = total_count

    @property
    def pages(self) -> int:
        return ceil(self.total_count / float(self.per_page))

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def prev(self) -> int | None:
        return self.page - 1 if self.has_prev else None

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    # pylint: disable=W1653
    @property
    def next(self) -> int | None:
        return self.page + 1 if self.has_next else None

    def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or (self.page - left_current - 1 < num < self.page + right_current)
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num


_NOT_WORD_RE = re.compile(r"[^\w\s]+", flags=re.UNICODE)


def slugify(value: str, separator: str = "-") -> str:
    """Slugify an Unicode string, to make it URL friendly."""
    if not isinstance(value, str):
        msg = "value must be a Unicode string"
        raise TypeError(msg)

    value = _NOT_WORD_RE.sub(" ", value)
    value = unicodedata.normalize("NFKD", value)
    bytes_value = value.encode("ascii", "ignore")
    value = bytes_value.decode("ascii")
    value = value.strip().lower()
    value = re.sub(rf"[{separator}_\s]+", separator, value)
    return value


class BasePresenter:
    """A presenter wraps a model an adds specific (often, web-centric)
    accessors.

    Subclass to make it useful. Presenters are immutable.
    """

    def __init__(self, model) -> None:
        self._model = model

    def __getattr__(self, key):
        return getattr(self._model, key)

    def __setattr__(self, key, value) -> None:
        """Make presenter immutable."""
        if key == "_model":
            self.__dict__[key] = value
        else:
            msg = "Can't set attribute on a presenter."
            raise AttributeError(msg)

    @classmethod
    def wrap_collection(cls, models):
        return [cls(model) for model in models]


def encode_string(string_or_bytes: str | bytes) -> bytes:
    """Encode a string to bytes, if it isn't already.

    :param string_or_bytes: The string to encode.
        Does nothing if it's already bytes.
    """
    # from pysecurity

    if isinstance(string_or_bytes, str):
        return string_or_bytes.encode()
    return string_or_bytes


def md5(data: str | bytes | None):
    """md5 function, as in flask-security."""
    # flask-security is not needed anywhere else and as of 1.7.5 has
    # strong dependency requirements that prevent us from upgrading a
    # few packages (flask-login 0.4).
    return hashlib.md5(encode_string(data or "")).hexdigest()  # noqa: S324
