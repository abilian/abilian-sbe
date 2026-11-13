# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import sqlalchemy as sa
from flask import Flask, g
from wtforms import Form, IntegerField, StringField

# Import for side effects (monkey-patch)
import abilian.web.forms
from abilian.core.entities import Entity
from abilian.web.forms.widgets import (
    EmailWidget,
    Panel,
    Row,
    SingleView,
    linkify_url,
    text2html,
)

# Dpnt' remove
assert abilian.web.forms


class WidgetTestModel(Entity):
    """Mock model."""

    __tablename__ = "widget_test_model"

    id = sa.Column(sa.Integer, primary_key=True)
    price = sa.Column(sa.Integer)
    email = sa.Column(sa.Text)

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self._display_value_called = False

    def display_value(self, attr: str) -> int | str:
        self._display_value_called = True
        return getattr(self, attr)


class DummyForm(Form):
    name = StringField("Nom du véhicule")
    price = IntegerField("Prix du véhicule")
    email = StringField("email", view_widget=EmailWidget())

    _groups = {"all": ["name", "price", "email"]}


def test_single_view(app: Flask) -> None:
    model = WidgetTestModel(name="Renault Megane", price=10000, email="joe@example.com")
    panels = [Panel("main", Row("name"), Row("price"), Row("email"))]
    form = DummyForm(obj=model)
    view = SingleView(form, *panels, view={"can_edit": False, "can_delete": False})
    res = view.render(model)

    assert "Renault Megane" in res
    assert "10000" in res
    # 'mailto:' is created by EmailWidget
    assert "mailto:joe@example.com" in res


def test_edit_view(app: Flask) -> None:
    g.view = {"buttons": []}

    model = WidgetTestModel(name="Renault Megane", price=10000)
    panels = [Panel("main", Row("name"), Row("price"))]
    form = DummyForm(obj=model)
    view = SingleView(form, *panels)
    res = view.render_form()

    # assert model._display_value_called
    assert "Renault Megane" in res
    assert "10000" in res


EXPECTED = (
    '<a href="http://example.com">example.com</a>'
    '&nbsp;<i class="fa fa-external-link"></i>'
)


def test_http() -> None:
    value = "http://example.com"
    result = linkify_url(value)
    assert result == EXPECTED


def test_no_http() -> None:
    value = "example.com"
    result = linkify_url(value)
    assert result == EXPECTED


def test1() -> None:
    result = text2html("a")
    assert result == "a"


def test2() -> None:
    result = text2html("a\nb")
    assert str(result) == "<p>a</p>\n<p>b</p>"


def test3() -> None:
    result = text2html("a\n\nb")
    assert str(result) == "<p>a</p>\n<p>b</p>"


def test4() -> None:
    result = text2html("a\n<a>toto</a>")
    assert str(result) == "<p>a</p>\n<p>&lt;a&gt;toto&lt;/a&gt;</p>"
