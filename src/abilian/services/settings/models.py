# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from abilian.core.extensions import db

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["Setting", "empty_value"]


class TransformerRegistry:
    def __init__(self) -> None:
        self.encoders: dict[str, Callable] = {}
        self.decoders: dict[str, Callable] = {}

    def encode(self, type_: str, value: Any) -> str:
        return self.encoders.get(type_, str)(value)

    def decode(self, type_: str, value: str) -> Any:
        decoder = self.decoders.get(type_)
        if decoder is not None:
            value = decoder(value)
        return value

    def register(
        self,
        type_: str,
        encoder: Callable | None = None,
        decoder: Callable | None = None,
    ) -> None:
        assert type_
        assert any((encoder, decoder))

        if encoder:
            self.encoders[type_] = encoder
        if decoder:
            self.decoders[type_] = decoder


_transformers = TransformerRegistry()


class _EmptyValue:
    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "<Empty Value>"


#: marker for emptiness, to distinguish from None
empty_value = _EmptyValue()


class Setting(db.Model):
    """A Setting is a very simple key/value object, key being a string
    identifier and the primary key.

    value must be stored as Unicode.
    """

    __tablename__ = "setting"

    transformers = _transformers
    key = sa.Column("key", sa.String(length=255), primary_key=True)

    #: Can be a string (Unicode), int, bool, json... or even a long dotted name
    #: if that's what you need. Type must be set before setting `value`
    _type = sa.Column("type", sa.String(length=1000), nullable=False)

    _value = sa.Column("value", sa.Text())

    @property
    def type(self) -> str:
        return self._type

    @type.setter
    def type(self, type_: str) -> None:
        if not (
            type_ in self.transformers.encoders and type_ in self.transformers.decoders
        ):
            msg = f'Invalid type "{type_}": no encoder and/or decoder registered'
            raise ValueError(msg)
        self._type = type_

    @property
    def value(self):
        if self._value is None:
            return empty_value

        assert isinstance(self._value, str)
        return self.transformers.decode(self.type, self._value)

    @value.setter
    def value(self, value) -> None:
        assert self.type
        self._value = self.transformers.encode(self.type, value)
        assert isinstance(self._value, str)


register = _transformers.register


def from_int(i: int) -> str:
    return f"{i}"


register("int", from_int, int)


def from_bool(b: bool) -> str:
    return "true" if b else "false"


def to_bool(s: str) -> bool:
    return s == "true"


register("bool", from_bool, to_bool)


def from_unicode(s: str) -> str:
    return s


def to_unicode(s: str) -> str:
    return s


register("string", from_unicode, to_unicode)


def from_obj(o: Any) -> str:
    return json.dumps(o)


def to_obj(s: str) -> Any:
    return json.loads(s)


register("json", from_obj, to_obj)


def from_timedelta(s: timedelta) -> str:
    return json.dumps({"days": s.days, "seconds": s.seconds})


def to_timedelta(s: str):
    return timedelta(**json.loads(s))


register("timedelta", from_timedelta, to_timedelta)
