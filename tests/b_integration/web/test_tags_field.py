# Copyright (c) 2012-2024, Abilian SAS

"""Tags are edited in a plain text box, as labels separated by semicolons."""

from __future__ import annotations

from typing import TYPE_CHECKING

from werkzeug.datastructures import MultiDict
from wtforms import Form

from abilian.web.tags.forms import TagsField

if TYPE_CHECKING:
    from abilian.app import Application
    from abilian.core.sqlalchemy import SQLAlchemy


class TagsForm(Form):
    tags = TagsField(ns="default")


def test_new_labels_become_tags_and_the_box_shows_them_again(
    app: Application, db: SQLAlchemy
) -> None:
    with app.test_request_context():
        form = TagsForm(formdata=MultiDict({"tags": " red; blue;; red "}), tags=set())

        assert {tag.label for tag in form.tags.data} == {"red", "blue"}
        assert 'value="blue; red"' in str(form.tags())
