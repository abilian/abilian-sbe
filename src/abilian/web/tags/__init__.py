# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from typing import TYPE_CHECKING

from .extension import TagsExtension

if TYPE_CHECKING:
    from flask import Flask

# __all__ = ["TagCriterion", "TagsExtension"]
__all__ = ["TagsExtension"]


def register_plugin(app: Flask) -> None:
    TagsExtension(app)
