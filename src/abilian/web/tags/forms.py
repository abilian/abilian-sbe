# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from flask import current_app
from wtforms import StringField
from wtforms.widgets import TextInput

from abilian.core.models.tag import Tag
from abilian.web.forms import Field, Form
from abilian.web.forms.filters import strip
from abilian.web.forms.validators import required
from abilian.web.forms.widgets import ListWidget


class TagsField(Field):
    """Handle tags selection on for a given :attr:`tags namespace<.Tag.ns>`.

    Usage::

      __tags__ = TagsField(ns='tags namespace')
    """

    multiple = True
    widget = TextInput()
    view_widget = ListWidget()

    def __init__(self, ns, *args, **kwargs) -> None:
        kwargs.setdefault("view_widget", self.view_widget)
        super().__init__(*args, **kwargs)
        self.ns = ns.strip()
        assert self.ns

    def iter_choices(self):
        choices = []
        extension = current_app.extensions["tags"]
        ns_tags = extension.get(ns=self.ns)

        for tag in ns_tags:
            choices.append((tag.label, tag.label, tag in self.data))

        # in case of error during form validation, don't forget new added tags
        for tag in self.data - set(ns_tags):
            choices.append((tag.label, tag.label, True))

        return sorted(choices)

    def default(self):
        return set()

    def _value(self) -> str:
        return "; ".join(sorted(tag.label for tag in self.data or ()))

    def process_data(self, data):
        data = {t for t in data if t.ns == self.ns}
        return super().process_data(data)

    def process_formdata(self, valuelist) -> None:
        extension = current_app.extensions["tags"]
        labels = {label.strip() for label in valuelist[0].split(";")} - {""}
        data = set()

        for label in labels:
            tag = extension.get(ns=self.ns, label=label)
            if tag is None:
                tag = Tag(ns=self.ns, label=label)
            data.add(tag)

        self.data = data

    def populate_obj(self, obj, name) -> None:
        extension = current_app.extensions["tags"]
        # all_tags is an InstrumentedSet. add/remove will result in DB
        # operations.
        all_tags = extension.entity_tags(obj)
        all_ns_tags = {t for t in extension.entity_tags(obj) if t.ns == self.ns}
        to_remove = all_ns_tags - self.data

        for tag in to_remove:
            all_tags.remove(tag)

        for tag in self.data:
            all_tags.add(tag)


_NS = StringField("Namespace", validators=[required()], filters=[strip])


class TagForm(Form):
    """Form for a single tag."""

    label = StringField("Label", filters=[strip], validators=[required()])


class TagNSForm(TagForm):
    """Allows to edit namespace."""

    ns = _NS
