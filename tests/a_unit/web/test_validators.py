# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import fixture, raises
from wtforms import Form, StringField
from wtforms.validators import ValidationError

from abilian.web.forms.validators import siret_validator

if TYPE_CHECKING:
    from collections.abc import Callable


class DummyForm(Form):
    name = StringField("foo")
    siret = StringField("Siret")


class DummyField:
    def __init__(self, data: str, errors=(), raw_data=None) -> None:
        self.data = data
        self.errors = list(errors)
        self.raw_data = raw_data


def error_message(validator: Callable, form: DummyForm, field: DummyField) -> str:
    try:
        validator(form, field)
    except ValidationError as e:
        return e.args[0]
    else:
        return ""


@fixture
def validator() -> Callable:
    return siret_validator()


def test_siret_validator_valid_1(validator: Callable) -> None:
    # valid
    form = DummyForm(siret="54207855500514", name="foo")
    field = form.siret
    assert validator(form, field) is None


def test_siret_validator_valid_2(validator: Callable) -> None:
    # valid
    form = DummyForm(siret="54207855500514", name="foo")
    field = form.siret
    assert validator(form, field) is None


def test_siret_validator_invalid_luhn(validator: Callable) -> None:
    # invalid Luhn (changed the first digit)
    form = DummyForm(siret="64207855500514", name="foo")
    field = form.siret
    with raises(ValidationError):
        validator(form, field)


def test_siret_validator_invalid_2(validator: Callable) -> None:
    # invalid
    form = DummyForm(siret="WRONG542078555", name="foo")
    field = form.siret
    with raises(ValidationError):
        validator(form, field)


def test_siret_validator_too_short(validator: Callable) -> None:
    # too short
    form = DummyForm(siret="54207", name="foo")
    field = form.siret
    with raises(ValidationError):
        validator(form, field)


def test_siret_ok() -> None:
    siret = siret_validator()
    form = DummyForm()
    assert siret(form, DummyField("78913349300013")) is None
    assert siret(form, DummyField("MONACOCONFO001")) is None

    # test other geographical exceptions; WARNING! the siret format is probably
    # not right, but we had no example in the spec; only geo codes...
    assert siret(form, DummyField("MONACOCONFO458")) is None
    assert siret(form, DummyField("MONACOCONFO462")) is None
    assert siret(form, DummyField("MONACOCONFO496")) is None
    assert siret(form, DummyField("MONACOCONFO372")) is None


def test_siret_ko_special_siret(validator: Callable) -> None:
    form = DummyForm()

    field = DummyField("MONACOCONFO999")
    with raises(ValidationError):
        validator(form, field)
    assert (
        error_message(validator, form, field)
        == "SIRET looks like special SIRET but geographical code seems invalid (999)"
    )


def test_siret_ko_invalid_length(validator: Callable) -> None:
    # invalid length
    form = DummyForm()
    field = DummyField("42342435")
    with raises(ValidationError):
        validator(form, field)
    assert (
        error_message(validator, form, field)
        == "SIRET must have exactly 14 characters (8)"
    )


def test_siret_ko_invalid_luhn(validator: Callable) -> None:
    # invalid checksum
    form = DummyForm()
    field = DummyField("78913349300011")
    with raises(ValidationError):
        validator(form, field)
    assert (
        error_message(validator, form, field)
        == "SIRET number is invalid (length is ok: verify numbers)"
    )
