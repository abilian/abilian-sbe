# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import operator
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any

import babel
import babel.dates
import sqlalchemy as sa
import sqlalchemy.exc
from flask import current_app
from flask_babel import get_timezone
from flask_login import current_user
from flask_wtf.file import FileField as BaseFileField
from loguru import logger
from wtforms import (
    Field,
    FieldList as BaseFieldList,
    FormField as BaseFormField,
    SelectField,
    SelectFieldBase,
    SelectMultipleField,
    ValidationError,
)
from wtforms.validators import DataRequired, Optional
from wtforms_alchemy import (
    ModelFieldList as BaseModelFieldList,
    ModelFormField as BaseModelFormField,
)
from wtforms_sqlalchemy.fields import has_identity_key

from abilian import i18n
from abilian.core.extensions import db
from abilian.core.util import utc_dt

from .widgets import DateInput, DateTimeInput, FileInput, SelectWidget

if TYPE_CHECKING:
    from babel.core import Locale
    from werkzeug.datastructures import ImmutableMultiDict

# FIXME
# Warning
# Deprecated since version 2.0:
#   wtforms.ext.appengine is deprecated and will be removed in WTForms 3.0.
#   Use WTForms-Appengine instead.


__all__ = [
    "ChoiceField",
    "DateField",
    "DateTimeField",
    "FileField",
    "FormField",
    "ModelFieldList",
    "MultipleChoiceField",
    "QuerySelectField",
]


class FormField(BaseFormField):
    """Discard csrf_token on subform."""

    def process(self, *args, **kwargs) -> None:
        super().process(*args, **kwargs)
        # FIXME
        # if isinstance(self.form, SecureForm):
        #     # don't create errors because of subtoken
        #     self._subform_csrf = self.form["csrf_token"]
        #     del self.form["csrf_token"]

    @property
    def data(self):
        # FIXME
        # if not isinstance(self.form, SecureForm):
        #     return self.form.data
        return self.form.data

        # SecureForm will try to pop 'csrf_token', but we removed it during
        # process
        # self.form._fields["csrf_token"] = self._subform_csrf
        # data = self.form.data
        # del self.form["csrf_token"]
        # return data


class ModelFormField(FormField, BaseModelFormField):
    """Discard csrf_token on subform."""


class FilterFieldListMixin:
    def validate(self, form, extra_validators=()):
        to_remove = []
        for field in self.entries:
            is_subform = isinstance(field, BaseFormField)
            data = field.data.values() if is_subform else [field.data]

            if not any(data):
                # all inputs empty: discard row
                to_remove.append(field)

        for field in to_remove:
            self.entries.remove(field)

        if self.entries:
            # setting raw_data enables validator to function properly
            # 1) we have entries so a subfield is not empty
            # 2) FieldList by default has an optional() validator
            # 3) by setting raw_data optional() does not reset the errors dict
            # -> subfields errors are propagated
            self.raw_data = [True]
        return super().validate(form, extra_validators)


class FieldList(FilterFieldListMixin, BaseFieldList):
    pass


class ModelFieldList(FilterFieldListMixin, BaseModelFieldList):
    """Filter empty entries before saving and refills before displaying."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # build visible field list for widget. We must do it during form
        # instanciation so as to have permission filtering
        field_names = []
        labels = []
        fieldsubform = self.unbound_field.bind(form=None, name="dummy", _meta=self.meta)
        subform = fieldsubform.form_class(csrf_enabled=False)
        for f in subform:
            if f.is_hidden:
                continue
            name = f.short_name
            field_names.append(name)
            labels.append(f.label.text if f.label else f.name)

        self._field_names = field_names
        self._field_labels = labels
        self._field_nameTolabel = dict(
            zip(self._field_names, self._field_labels, strict=True)
        )

    def __call__(self, **kwargs):
        """Refill with default min_entry, which were possibly removed by
        FilterFieldListMixin.

        Mandatory for proper function of DynamicRowWidget which clones
        an existing field
        """
        while len(self) < self.min_entries:
            self.append_entry()
        return super().__call__(**kwargs)


class FileField(BaseFileField):
    """Support 'multiple' attribute, enabling html5 multiple file input in
    widget.

    Can store file using a related model.

    :param blob_attr: attribute name to store / retrieve value on related model.
      Used if `name` is a relationship on model. Defauts to `'value'`
    """

    multiple = False
    widget = FileInput()
    blob = None
    blob_attr = "value"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        try:
            self.multiple = kwargs.pop("multiple")
        except KeyError:
            self.multiple = False

        self.blob_attr = kwargs.pop("blob_attr", self.__class__.blob_attr)
        allow_delete = kwargs.pop("allow_delete", None)
        validators = list(kwargs.get("validators", []))
        self.upload_handles = []
        self.delete_files_index = []
        self._has_uploads = False

        if allow_delete is not None:
            if any(
                isinstance(v, DataRequired if allow_delete else Optional)
                for v in validators
            ):
                msg = (
                    "Field validators are conflicting with `allow_delete`,"
                    f"validators={validators!r}, allow_delete={allow_delete!r}"
                )
                raise ValueError(msg)
            if not allow_delete:
                validators.append(DataRequired())

        kwargs["validators"] = validators
        super().__init__(*args, **kwargs)

    @property
    def allow_delete(self) -> bool:
        """Property for legacy code.

        Test `field.flags.required` instead.
        """
        return not self.flags.required

    def __call__(self, **kwargs):
        if "multiple" not in kwargs and self.multiple:
            kwargs["multiple"] = "multiple"
        return super().__call__(**kwargs)

    def has_file(self):
        return self._has_uploads

    def process(self, formdata: ImmutableMultiDict, *args, **kwargs):
        delete_arg = f"__{self.name}_delete__"
        self.delete_files_index = (
            formdata.getlist(delete_arg) if formdata and delete_arg in formdata else []
        )

        return super().process(formdata, *args, **kwargs)

    def process_data(self, value: None):
        if isinstance(value, db.Model):
            self.blob = value
            value = getattr(value, self.blob_attr)

        self.object_data = value
        return super().process_data(value)

    def process_formdata(self, valuelist: list[str]) -> None:
        uploads = current_app.extensions["uploads"]
        if self.delete_files_index:
            self.data = None
            return

        if valuelist:
            self.upload_handles = valuelist
            handle = valuelist[0]
            fileobj = uploads.get_file(current_user, handle)

            if fileobj is None:
                # FIXME: this is a validation task
                msg = f"File with handle {handle!r} not found"
                raise ValueError(msg)

            meta = uploads.get_metadata(current_user, handle)
            filename = meta.get("filename", handle)
            mimetype = meta.get("mimetype")
            stream = fileobj.open("rb")
            stream.filename = filename
            if mimetype:
                stream.content_type = mimetype
                stream.mimetype = mimetype
            self.data = stream
            self._has_uploads = True

    def populate_obj(self, obj, name) -> None:
        """Store file."""
        from abilian.core.models.blob import Blob

        delete_value = self.allow_delete and self.delete_files_index

        if not self.has_file() and not delete_value:
            # nothing uploaded, and nothing to delete
            return

        state = sa.inspect(obj)
        mapper = state.mapper
        if name not in mapper.relationships:
            # directly store in the database
            super().populate_obj(obj, name)
            return

        rel = getattr(mapper.relationships, name)
        if rel.uselist:
            msg = "Only single target supported; else use ModelFieldList"
            raise ValueError(msg)

        if delete_value:
            setattr(obj, name, None)
            return

        #  FIXME: propose option to always create a new blob
        cls = rel.mapper.class_
        val = getattr(obj, name)

        if val is None:
            val = cls()
            setattr(obj, name, val)

        data = ""
        if self.has_file():
            data = self.data
            if not issubclass(cls, Blob):
                data = data.read()

        setattr(val, self.blob_attr, data)


#: What the browser's date and time inputs send, whatever the user's locale.
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = f"{DATE_FORMAT} %H:%M"


class DateTimeField(Field):
    """A date and a time, entered in two native inputs that share its name."""

    widget = DateTimeInput()

    def __init__(
        self,
        label: str | None = None,
        validators: Any = None,
        use_naive: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        :param use_naive: if `False`, dates are considered entered using user's
        timezone; different users with different timezones will see corrected
        date/time. For storage dates are always stored using UTC.
        """
        self.raw_data = kwargs.pop("raw_data", None)
        super().__init__(label, validators, **kwargs)
        self.use_naive = use_naive

    def _value(self) -> str:
        if self.raw_data:
            return " ".join(self.raw_data)
        return self.data.strftime(DATETIME_FORMAT) if self.data else ""

    def process_data(self, value: datetime) -> None:
        if value is not None:
            if not value.tzinfo:
                if self.use_naive:
                    value = get_timezone().localize(value)
                else:
                    value = utc_dt(value)
            if not self.use_naive:
                value = value.astimezone(get_timezone())

        super().process_data(value)

    def process_formdata(self, valuelist: list[str]) -> None:
        if valuelist:
            try:
                self.data = datetime.strptime(" ".join(valuelist), DATETIME_FORMAT)
                if not self.use_naive:
                    tz = get_timezone()
                    if self.data.tzinfo:
                        self.data = self.data.astimezone(tz)
                    else:
                        self.data = tz.localize(self.data)

                # convert to UTC
                self.data = utc_dt(self.data)
            except ValueError as e:
                self.data = None
                raise ValueError(self.gettext("Not a valid datetime value")) from e

    def populate_obj(self, obj: Any, name: str) -> None:
        dt = self.data
        if dt and self.use_naive:
            dt = dt.replace(tzinfo=None)

        setattr(obj, name, dt)


class DateField(Field):
    """A `date`, entered in a native date input."""

    widget = DateInput()

    def __init__(
        self, label: str | None = None, validators: Any = None, **kwargs: Any
    ) -> None:
        super().__init__(label, validators, **kwargs)

    def _value(self) -> str:
        if self.raw_data:
            return " ".join(self.raw_data)
        return self.data.strftime(DATE_FORMAT) if self.data else ""

    def process_formdata(self, valuelist: list[str]) -> None:
        valuelist = [i for i in valuelist if i.strip()]

        if valuelist:
            try:
                self.data = datetime.strptime(" ".join(valuelist), DATE_FORMAT).date()
            except (ValueError, TypeError) as e:
                self.data = None
                raise ValueError(self.gettext("Not a valid datetime value")) from e
        else:
            self.data = None


class ChoiceField(SelectField):
    """A select with a read-only rendering. `choices` can be a function."""

    widget = SelectWidget()


class MultipleChoiceField(SelectMultipleField):
    widget = SelectWidget(multiple=True)
    multiple = True


class QuerySelectField(SelectFieldBase):
    """COPY/PASTED (and patched) from WTForms!

    Will display a select drop-down field to choose between ORM results in a
    sqlalchemy `Query`.  The `data` property actually will store/keep an ORM
    model instance, not the ID. Submitting a choice which is not in the query
    will result in a validation error.

    This field only works for queries on models whose primary key column(s)
    have a consistent string representation. This means it mostly only works
    for those composed of string and integer types. For the most
    part, the primary keys will be auto-detected from the model, alternately
    pass a one-argument callable to `get_pk` which can return a unique
    comparable key.

    The `query` property on the field can be set from within a view to assign
    a query per-instance to the field. If the property is not set, the
    `query_factory` callable passed to the field constructor will be called to
    obtain a query.

    Specify `get_label` to customize the label associated with each option. If
    a string, this is the name of an attribute on the model object to use as
    the label text. If a one-argument callable, this callable will be passed
    model instance and expected to return the label text. Otherwise, the model
    object's `__str__` or `__unicode__` will be used.

    :param allow_blank: DEPRECATED. Use optional()/required() validators instead.
    """

    def __init__(
        self,
        label=None,
        validators=None,
        *,
        query_factory=None,
        get_pk=None,
        get_label=None,
        allow_blank=False,
        blank_text="",
        widget=None,
        multiple=False,
        collection_class=list,
        **kwargs,
    ) -> None:
        if widget is None:
            widget = SelectWidget(multiple=multiple)

        kwargs["widget"] = widget
        self.multiple = multiple
        self.collection_class = collection_class

        if validators is None:
            validators = []

        if not any(isinstance(v, (Optional, DataRequired)) for v in validators):
            logger.warning(
                'Use deprecated parameter `allow_blank` for field "{label}".',
                label=label,
            )
            if not allow_blank:
                validators.append(DataRequired())

        super().__init__(label, validators, **kwargs)

        # PATCHED!
        if query_factory:
            self.query_factory = query_factory

        if get_pk is None:
            if not has_identity_key:
                msg = "The sqlalchemy identity_key function could not be imported."
                raise Exception(msg)
            self.get_pk = self._get_pk_from_identity
        else:
            self.get_pk = get_pk

        match get_label:
            case None:
                self.get_label = lambda x: x
            case str():
                self.get_label = operator.attrgetter(get_label)
            case _:
                self.get_label = get_label

        self.allow_blank = allow_blank
        self.blank_text = blank_text
        self.query = None
        self._object_list = None

    @staticmethod
    def _get_pk_from_identity(obj):
        """Copied / pasted, and fixed, from WTForms_sqlalchemy due to issue w/
        SQLAlchemy >= 1.2."""
        from sqlalchemy.orm.util import identity_key

        _cls, key = identity_key(instance=obj)[0:2]
        return ":".join(str(x) for x in key)

    def _get_data(self):
        formdata = self._formdata
        if formdata is not None:
            if not self.multiple:
                formdata = [formdata]
            formdata = set(formdata)
            data = [obj for pk, obj in self._get_object_list() if pk in formdata]
            if all(hasattr(x, "name") for x in data):
                data = sorted(data, key=lambda x: x.name)
            else:
                data = sorted(data, key=str)

            if data:
                if not self.multiple:
                    data = data[0]
                self._set_data(data)
        return self._data

    def _set_data(self, data) -> None:
        if self.multiple and not isinstance(data, self.collection_class):
            data = self.collection_class(data) if data else self.collection_class()
        self._data = data
        self._formdata = None

    data = property(_get_data, _set_data)

    def _get_object_list(self):
        if self._object_list is None:
            query = self.query or self.query_factory()
            get_pk = self.get_pk
            self._object_list = [(str(get_pk(obj)), obj) for obj in query]
        return self._object_list

    def iter_choices(self):
        # Nothing selected already means blank in a multiple select.
        if not self.flags.required and not self.multiple:
            yield (None, None, self.data is None)

        predicate = (
            operator.contains
            if (self.multiple and self.data is not None)
            else operator.eq
        )
        # remember: operator.contains(b, a) ==> a in b
        # so: obj in data ==> contains(data, obj)
        predicate = partial(predicate, self.data)

        for pk, obj in self._get_object_list():
            yield (pk, self.get_label(obj), predicate(obj))

    def process_formdata(self, valuelist) -> None:
        if not valuelist:
            self.data = [] if self.multiple else None
        else:
            self._data = None
            if not self.multiple:
                valuelist = valuelist[0]
            self._formdata = valuelist

    def pre_validate(self, form) -> None:
        if not self.allow_blank or self.data is not None:
            data = self.data
            if not self.multiple:
                data = [data] if data is not None else []
            elif not data:
                # multiple values: ensure empty list (data may be None)
                data = []

            data = set(data)
            valid = {obj for pk, obj in self._get_object_list()}
            if data - valid:
                raise ValidationError(self.gettext("Not a valid choice"))


class LocaleSelectField(SelectField):
    widget = SelectWidget()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["coerce"] = LocaleSelectField.coerce
        kwargs["choices"] = list(i18n.supported_app_locales())
        super().__init__(*args, **kwargs)

    @staticmethod
    def coerce(value: Locale | None) -> Locale | None:
        match value:
            case babel.Locale():
                return value
            case str():
                return babel.Locale.parse(value)
            case None:
                return None

        msg = f"Value cannot be converted to Locale(), or is not None, {value!r}"
        raise ValueError(msg)

    def iter_choices(self):
        if not self.flags.required:
            yield (None, None, self.data is None)

        for locale, label in i18n.supported_app_locales():
            yield (locale.language, label.capitalize(), locale == self.data)


class TimezoneField(SelectField):
    widget = SelectWidget()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["coerce"] = babel.dates.get_timezone
        kwargs["choices"] = list(i18n.timezones_choices())
        super().__init__(*args, **kwargs)

    def iter_choices(self):
        if not self.flags.required:
            yield (None, None, self.data is None)

        for tz, label in i18n.timezones_choices():
            yield (tz.zone, label, tz == self.data)
