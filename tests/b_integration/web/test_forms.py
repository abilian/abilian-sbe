# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from unittest import mock

import pytest
import pytz
from wtforms import Form

from abilian.core.entities import Entity
from abilian.services.security import ANONYMOUS, OWNER, READ, WRITE, Role
from abilian.web.forms import FormPermissions, fields, filters

if TYPE_CHECKING:
    from abilian.app import Application


def user_tz() -> str:
    # This one is GMT+8 and has no DST (tests should pass any time in year)
    return "Asia/Hong_Kong"


USER_TZ = pytz.timezone(user_tz())


# test filters
def test_strip() -> None:
    strip = filters.strip
    assert strip(None) == ""
    assert strip(4) == 4
    assert strip(" a string ") == "a string"
    assert strip(" voilà ") == "voilà"


def test_uppercase() -> None:
    uppercase = filters.uppercase
    assert uppercase(None) is None
    assert uppercase(4) == 4
    assert uppercase(" a string ") == " A STRING "
    assert uppercase(" Voilà ") == " VOILÀ "


def test_lowercase() -> None:
    lowercase = filters.lowercase
    assert lowercase(None) is None
    assert lowercase(4) == 4
    assert lowercase(" A STRING ") == " a string "
    assert lowercase(" VOILÀ ") == " voilà "


# FormPermissions
# @pytest.mark.skip(reason="Need to be updated")
def test_form_permissions_controller() -> None:
    security_mock = mock.Mock()
    has_role = security_mock.has_role = mock.Mock()
    has_role.return_value = True

    current_app_mock = mock.Mock()
    current_app_mock.services = {"security": security_mock}

    MarkRole = Role("tests:mark-role")
    _MARK = object()
    _ENTITY_MARK = Entity()

    with mock.patch("abilian.services.current_app", current_app_mock):
        # default role
        fp = FormPermissions()
        assert fp.has_permission(READ)
        assert fp.has_permission(READ, obj=_MARK)
        assert fp.has_permission(READ, obj=_ENTITY_MARK)

        # change default
        fp = FormPermissions(default=MarkRole)
        assert fp.has_permission(READ)
        assert fp.has_permission(READ, field="test")

        fp = FormPermissions(default=MarkRole, read=ANONYMOUS)
        assert fp.has_permission(READ)
        assert fp.has_permission(READ, field="test")
        assert fp.has_permission(WRITE)

        # field roles
        fp = FormPermissions(
            default=MarkRole, read=ANONYMOUS, fields_read={"test": {OWNER}}
        )
        assert fp.has_permission(READ)
        assert fp.has_permission(READ, field="test")
        assert fp.has_permission(READ, field="test")

        # dynamic roles
        dyn_roles = mock.Mock()
        dyn_roles.return_value = [MarkRole]
        fp = FormPermissions(read=dyn_roles)
        assert fp.has_permission(READ)
        assert dyn_roles.call_args == [{"permission": READ, "field": None, "obj": None}]

        dyn_roles.reset_mock()
        fp = FormPermissions(read=[OWNER, dyn_roles])
        assert fp.has_permission(READ)
        assert dyn_roles.call_args == [{"permission": READ, "field": None, "obj": None}]


def patch_babel(app: Application) -> None:
    app.extensions["babel"].timezone_selector_func = None
    app.extensions["babel"].timezoneselector(user_tz)


def test_datetime_field(app: Application) -> None:
    """Test fields supports date with year < 1900."""

    assert "fr" in app.config["BABEL_ACCEPT_LANGUAGES"]

    patch_babel(app)

    obj = mock.Mock()

    headers = {"Accept-Language": "fr-FR,fr;q=0.8"}
    with app.test_request_context(headers=headers):
        field = fields.DateTimeField(use_naive=False).bind(Form(), "dt")
        field.process_formdata(["1789-06-17", "10:42"])
        # 1789: applied offset for HongKong is equal to LMT+7:37:00,
        # thus we compare with tzinfo=user_tz
        expected_datetime = dt.datetime(1789, 6, 17, 10, 42, tzinfo=USER_TZ)
        assert field.data == expected_datetime
        # UTC stored
        assert field.data.tzinfo is pytz.UTC

        # non-naive mode: test process_data change TZ to user's TZ
        field.process_data(field.data)
        assert field.data.tzinfo is USER_TZ
        assert field.data == expected_datetime
        # displayed in user current timezone
        field.raw_data = None
        assert field._value() == "1789-06-17 10:42"

        field.populate_obj(obj, "dt")
        assert obj.dt == expected_datetime

        # test more recent date: offset is GMT+8
        field.process_formdata(["2011-01-23", "10:42"])
        expected_datetime = dt.datetime(2011, 1, 23, 2, 42, tzinfo=pytz.utc)
        assert field.data == expected_datetime


def test_datetime_field_naive(app: Application) -> None:
    """Test fields supports date with year < 1900."""
    patch_babel(app)

    obj = mock.Mock()

    headers = {"Accept-Language": "fr-FR,fr;q=0.8"}
    with app.test_request_context(headers=headers):
        # NAIVE mode: dates without timezone. Those are the problematic ones
        # when year < 1900: strptime will raise an Exception use naive dates; by
        # default
        field = fields.DateTimeField().bind(Form(), "dt")
        field.process_formdata(["1789-06-17", "10:42"])

        # UTC stored
        assert field.data.tzinfo is pytz.UTC
        expected_datetime = dt.datetime(1789, 6, 17, 10, 42, tzinfo=pytz.UTC)
        assert field.data == expected_datetime

        # naive stored
        field.populate_obj(obj, "dt")
        assert obj.dt == dt.datetime(1789, 6, 17, 10, 42)


@pytest.mark.parametrize("language", ["en", "fr"])
def test_datetime_field_renders_native_inputs_whatever_the_locale(
    app: Application, language: str
) -> None:
    """The browser sends ISO values and localises the display itself, so the
    markup must not follow the locale ('en' writes 1/23/11, 'fr' 23/01/2011)."""
    patch_babel(app)

    with app.test_request_context(headers={"Accept-Language": language}):
        field = fields.DateTimeField().bind(Form(), "dt")
        field.process(None, dt.datetime(2011, 1, 23, 10, 42))
        html = field()

    assert 'type="date"' in html
    assert 'value="2011-01-23"' in html
    assert 'type="time"' in html
    assert 'value="10:42"' in html
    assert html.count('name="dt"') == 2


def test_datetime_field_keeps_a_suggested_time_without_a_date(
    app: Application,
) -> None:
    """A new event suggests a time and leaves the day blank."""
    with app.test_request_context():
        field = fields.DateTimeField(raw_data=["", "09:00"]).bind(Form(), "dt")
        field.process(None)
        html = field()

    assert 'type="date"' in html
    assert 'value=""' in html
    assert 'value="09:00"' in html


def test_datetime_field_rejects_a_missing_date(app: Application) -> None:
    with app.test_request_context():
        field = fields.DateTimeField().bind(Form(), "dt")
        with pytest.raises(ValueError, match="Not a valid datetime value"):
            field.process_formdata(["", "09:00"])


def test_date_field(app: Application) -> None:
    """Test fields supports date with year < 1900."""
    patch_babel(app)

    headers = {"Accept-Language": "fr-FR,fr;q=0.8"}
    with app.test_request_context(headers=headers):
        field = fields.DateField().bind(Form(), "dt")
        field.process_formdata(["1789-06-17"])
        assert field.data == dt.date(1789, 6, 17)

        field.raw_data = None
        assert field._value() == "1789-06-17"
        assert 'type="date"' in field()
