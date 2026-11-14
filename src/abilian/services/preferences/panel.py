# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask.typing import ResponseReturnValue


class PreferencePanel:
    """Base class for preference panels.

    Currently, this class does nothing. I may be useful in the future
    either as just a marker interface (for automatic plugin discovery /
    registration), or to add some common functionnalities. Otherwise, it
    will be removed.
    """

    id: str
    label: Any

    def is_accessible(self) -> bool:
        return True

    def get(self) -> ResponseReturnValue:
        raise NotImplementedError

    def post(self) -> ResponseReturnValue:
        raise NotImplementedError
