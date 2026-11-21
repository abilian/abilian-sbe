# Copyright (c) 2012-2024, Abilian SAS

"""
Special loggers
---------------

Changing `patch_logger` logging level must be done very early, because it may
emit logging during imports. Ideally, it should be the very first action in
your entry point before anything has been imported:

.. code-block:: python

 import logging
 logging.getLogger('PATCH').setLevel(logging.INFO)

"""

from __future__ import annotations

import logging

__all__ = ["patch_logger"]

_mk_fmt = "[%(name)s] %(message)s at %(pathname)s:%(lineno)d"
_mk_format = logging.Formatter(fmt=_mk_fmt)

_patch_handler = logging.StreamHandler()
_patch_handler.setFormatter(_mk_format)
_patch_logger = logging.getLogger("PATCH")
_patch_logger.addHandler(_patch_handler)
_patch_logger.propagate = False

if _patch_logger.level is logging.NOTSET:
    _patch_logger.setLevel(logging.WARNING)


class PatchLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        if isinstance(msg, str):
            return super().process(msg, kwargs)

        func = msg
        location = func.__module__
        if hasattr(func, "im_class"):
            cls = func.__self__.__class__
            func = func.__func__
            location = f"{cls.__module__}.{cls.__name__}"

        return f"{location}.{func.__name__}", kwargs


#: logger for monkey patchs. use like this:
#: patch_logger.info(<func>`patched_func`)
patch_logger = PatchLoggerAdapter(_patch_logger, {})
