# Copyright (c) 2012-2024, Abilian SAS

"""Field filters for WTForm."""

from __future__ import annotations

__all__ = ["lowercase", "strip", "uppercase"]


def strip(data: int | str | None) -> int | str:
    """Strip data if data is a string."""
    if data is None:
        return ""
    if not isinstance(data, str):
        return data
    return data.strip()


def uppercase(data: int | str | None) -> int | str | None:
    if not isinstance(data, str):
        return data
    return data.upper()


def lowercase(data: int | str | None) -> int | str | None:
    if not isinstance(data, str):
        return data
    return data.lower()
