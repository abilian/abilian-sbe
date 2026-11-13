# Copyright (c) 2012-2024, Abilian SAS

"""Class based views."""

from __future__ import annotations

import contextlib
from typing import Any, ClassVar, Never, Protocol

import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm
from flask import current_app, flash, g, redirect, render_template, request, url_for
from loguru import logger
from werkzeug.exceptions import BadRequest, NotFound
from wtforms import Form

from abilian.core.entities import ValidationError
from abilian.core.extensions import db
from abilian.core.signals import activity
from abilian.i18n import _, _l
from abilian.services import get_service
from abilian.services.security import CREATE, DELETE, READ, WRITE
from abilian.web import csrf, forms, nav
from abilian.web.action import ButtonAction, Endpoint, actions

from .base import JSONView, View


class ViewedModel(Protocol):
    """What the object views need of a model: an id, and a query on the class."""

    id: Any
    query: ClassVar[Any]


class BaseObjectView[M: ViewedModel](View):
    """Base class common to all database objects views."""

    #: form title
    title: str

    #: Model class
    Model: type[M]

    #: primary key name to look for in url arguments
    pk = "object_id"

    #: object instance for this view
    obj: M

    #: object id
    object_id: int

    #: template to render
    template: str

    #: default templates inherit from "base_template". This allows to use
    #: generic templates with a custom base
    base_template = "base.html"

    def __init__(
        self, Model=None, pk=None, base_template=None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        cls = self.__class__
        self.pk = pk if pk is not None else cls.pk
        self.Model = Model if Model is not None else cls.Model
        self.base_template = (
            base_template if base_template is not None else cls.base_template
        )

    def prepare_args(self, args, kwargs):
        args, kwargs = self.init_object(args, kwargs)

        if self.obj is None:
            raise NotFound

        return args, kwargs

    def breadcrumb(self) -> None:
        """Return :class:`..nav.BreadcrumbItem` instance for this object.

        This method may return a list of BreadcrumbItem instances.
        Return `None` if nothing.
        """
        return

    def init_object(self, args, kwargs):
        """This method is reponsible for setting :attr:`obj`.

        It is called during :meth:`prepare_args`.
        """
        self.object_id = kwargs.pop(self.pk, None)
        if self.object_id is not None:
            self.obj = self.Model.query.get(self.object_id)
            actions.context["object"] = self.obj

        return args, kwargs

    def get(self, *args, **kwargs):
        bc = self.breadcrumb()
        if bc is not None:
            bc = [bc] if isinstance(bc, nav.BreadcrumbItem) else list(bc)
            assert all(isinstance(b, nav.BreadcrumbItem) for b in bc)
            g.breadcrumb.extend(bc)

        kwargs = {"base_template": self.base_template}
        kwargs.update(self.template_kwargs)
        # forbid override "view"
        kwargs["view"] = self
        return render_template(self.template, **kwargs)

    @property
    def template_kwargs(self):
        """Get template render arguments.

        You may override `base_template` for instance. Only `view`
        cannot be overriden.
        """
        return {}


class ObjectView[M: ViewedModel, F: Form](BaseObjectView[M]):
    """View objects."""

    #: html template
    template = "default/object_view.html"

    #: View form class. Form object used to show objects fields
    Form: type[F]

    #: required permission. Must be an instance of
    #: :class:`abilian.services.security.Permission`
    permission = READ

    #: form instance for this view
    form: F

    def __init__(
        self, Model=None, pk=None, Form=None, template=None, *args, **kwargs
    ) -> None:
        super().__init__(Model, pk, *args, **kwargs)
        cls = self.__class__
        self.Form = Form if Form is not None else cls.Form
        self.template = template if template is not None else cls.template

    def prepare_args(self, args, kwargs):
        """
        :attr:`form` is initialized here. See also :meth:`View.prepare_args`.
        """
        args, kwargs = super().prepare_args(args, kwargs)
        form_kwargs = self.get_form_kwargs()
        self.form = self.Form(**form_kwargs)
        return args, kwargs

    def get_form_kwargs(self) -> dict[str, Any]:
        kw: dict[str, Any] = {"obj": self.obj}
        if issubclass(self.Form, forms.Form) and self.permission:
            kw["permission"] = self.permission
        return kw

    def index_url(self):
        return url_for(".index")

    def redirect_to_index(self):
        return redirect(self.index_url())

    @property
    def template_kwargs(self):
        """Provides :attr:`form` to templates."""
        kw = super().template_kwargs
        kw["form"] = self.form
        return kw


CANCEL_BUTTON = ButtonAction(
    "form",
    "cancel",
    title=_l("Cancel"),
    btn_class="default cancel",
)

EDIT_BUTTON = ButtonAction("form", "edit", btn_class="primary", title=_l("Save"))

ADD_ANOTHER_BUTTON = ButtonAction(
    "form",
    "create_add_another",
    btn_class="primary",
    title=_l("Create and add another"),
    condition=lambda ctx: getattr(ctx["view"], "add_another_button", False),
)


class ObjectEdit[M: ViewedModel, F: Form](ObjectView[M, F]):
    """Edit object."""

    template = "default/object_edit.html"
    decorators = (csrf.support_graceful_failure,)
    permission = WRITE

    #: :class:ButtonAction instance to show on form
    _buttons = ()

    #: submitted form data
    data = None

    #: action name from form data
    action = None

    #: button clicked, corresponding to :attr:`action`.
    button = None

    #: verb used to describe activity
    activity_verb = "update"

    #: UI flash message
    _message_success = _l("Entity successfully edited")

    view_endpoint = None

    def __init__(
        self,
        Model=None,
        pk=None,
        Form=None,
        *args,
        template=None,
        view_endpoint=None,
        message_success=None,
        **kwargs,
    ) -> None:
        super().__init__(Model, pk, Form, *args, template=template, **kwargs)
        if view_endpoint is not None:
            self.view_endpoint = view_endpoint

        if not self.view_endpoint:
            self.view_endpoint = f".{self.Model.__name__}_view"

        if message_success:
            self._message_success = message_success

    def post(self, *args, **kwargs):
        # conservative: no action submitted -> cancel
        action = self.data.get("__action", "cancel")
        if action == "cancel":
            return self.cancel()

        return self.handle_action(action)

    def put(self):
        return self.post()

    def prepare_args(self, args, kwargs):
        args, kwargs = super().prepare_args(args, kwargs)
        self._buttons = self.get_form_buttons(*args, **kwargs)
        self.data = request.form
        return args, kwargs

    def get_form_buttons(self, *args, **kwargs):
        return [EDIT_BUTTON, CANCEL_BUTTON]

    @property
    def buttons(self):
        return (button for button in self._buttons if button.available(actions.context))

    def view_url(self):
        kw = {self.pk: self.obj.id}
        return url_for(self.view_endpoint, **kw)

    def redirect_to_view(self):
        if self.button:
            url = self.button.url(actions.context)
            if url:
                return redirect(url)
        return redirect(self.view_url())

    def message_success(self):
        return str(self._message_success)

    # actions
    def handle_action(self, action):
        for button in self._buttons:
            if action == button.name:
                if not button.available({"view": self}):
                    msg = f'Action "{action.encode("utf-8")}" not available'
                    raise ValueError(msg)
                break
        else:
            msg = f'Unknown action: "{action.encode("utf-8")}"'
            raise ValueError(msg)

        self.action = action
        self.button = button
        return getattr(self, action)()

    def cancel(self):
        return self.redirect_to_view()

    def edit(self, redirect_to=None):
        if self.validate():
            return self.form_valid(redirect_to=redirect_to)
        if request.csrf_failed:
            errors = self.form.errors
            csrf_failed = errors.pop("csrf_token", False)
            if csrf_failed and not errors:
                # failed only because of invalid/expired csrf, no error on
                # form
                return self.form_csrf_invalid()

        resp = self.form_invalid()
        if resp:
            return resp

        flash(_("Please fix the error(s) below"), "error")

        # if we end here then something wrong has happened: show form with error
        # messages
        return self.get()

    def before_populate_obj(self) -> None:
        """This method is called after form has been validated and before
        calling `form.populate_obj()`.

        Sometimes one may want to remove a field
        from the form because it's non-sense to store it on edited object, and
        use it in a specific manner, for example::

            image = form.image
            del form.image
            store_image(image)
        """

    def after_populate_obj(self) -> None:
        """Called after `self.obj` values have been updated, and `self.obj`
        attached to an ORM session."""

    def handle_commit_exception(self, exc) -> None:
        """Hook point to handle exception that may happen during commit.

        It is the responsability of this method to perform a rollback if it is
        required for handling `exc`. If the method does not handle `exc` if should
        do nothing and return None.

        :returns: * a valid :class:`Response` if exception is handled.
                  * `None` if exception is not handled. Default handling happens.
        """
        return

    def commit_success(self) -> None:
        """Called after object has been successfully saved to database."""

    def validate(self):
        return self.form.validate()

    def form_valid(self, redirect_to=None):
        """Save object.

        Called when form is validated.

        :param redirect_to: real url (created with url_for) to redirect to,
          instead of the view by default.
        """
        session = db.session()

        with session.no_autoflush:
            self.before_populate_obj()
            self.form.populate_obj(self.obj)
            session.add(self.obj)
            self.after_populate_obj()

        try:
            session.flush()
            self.send_activity()
            session.commit()

        except ValidationError as e:
            rv = self.handle_commit_exception(e)
            if rv is not None:
                return rv
            session.rollback()
            flash(str(e), "error")
            return self.get()

        except sa.exc.IntegrityError as e:
            rv = self.handle_commit_exception(e)
            if rv is not None:
                return rv
            session.rollback()
            logger.error(str(e))
            flash(_("An entity with this name already exists in the system."), "error")
            return self.get()

        else:
            self.commit_success()
            flash(self.message_success(), "success")

            if redirect_to:
                return redirect(redirect_to)
            return self.redirect_to_view()

    def form_invalid(self) -> None:
        """When a form doesn't validate this method is called.

        It may return a :class:`Flask.Response` instance, to handle specific
        errors in custom screens.

        Else the edit form screen is returned with error(s) highlighted.

        This method is useful for detecting edition conflict using hidden fields
        and show a specific screen to help resolve the conflict.
        """
        return

    def form_csrf_invalid(self):
        """Called when a form doesn't validate *only* because of csrf token
        expiration.

        This works only if form is an instance of :class:`flask_wtf.form.SecureForm`.
        Else default CSRF protection (before request) will take place.

        It must return a valid :class:`Flask.Response` instance. By default it
        returns to edit form screen with an informative message.
        """
        current_app.extensions["csrf-handler"].flash_csrf_failed_message()
        return self.get()

    def send_activity(self) -> None:
        activity.send(
            self,
            actor=g.user,
            verb=self.activity_verb,
            object=self.obj,
            target=self.activity_target,
        )

    @property
    def activity_target(self) -> None:
        """Return `target` to use when creating activity."""
        return


CREATE_BUTTON = ButtonAction("form", "create", btn_class="primary", title=_l("Create"))
CHAIN_CREATE_BUTTON = ButtonAction(
    "form",
    "chain_create",
    btn_class="primary",
    title=_l("Create and add new"),
    endpoint=lambda ctx: Endpoint(request.endpoint, **request.view_args),
    condition=lambda ctx: getattr(ctx["view"], "chain_create_allowed", False),
)


class ObjectCreate[M: ViewedModel, F: Form](ObjectEdit[M, F]):
    """Create a new object."""

    permission = CREATE
    activity_verb = "post"
    _message_success = _l("Entity successfully added")

    #: set to `True` to show 'Save and add new' button
    chain_create_allowed = False

    def __init__(self, chain_create_allowed=None, *args, **kwargs) -> None:
        if chain_create_allowed is not None:
            self.chain_create_allowed = bool(chain_create_allowed)

        super().__init__(*args, **kwargs)

    def prepare_args(self, args, kwargs):
        # we must ensure that no flush() occurs and that obj is not registered
        # in session (to prevent accidental insert of an incomplete object)
        session = db.session()
        with session.no_autoflush:
            args, kwargs = super().prepare_args(args, kwargs)

        # obj may not be in session
        with contextlib.suppress(sa.exc.InvalidRequestError):
            session.expunge(self.obj)

        return args, kwargs

    def init_object(self, args, kwargs):
        self.obj = self.Model()
        return args, kwargs

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        if request.method == "GET":
            # when GET allow form prefill instead of empty/current object data
            # FIXME: filter allowed parameters on given a field flags (could be
            # 'allow_from_get'?)
            kw["formdata"] = request.args

        return kw

    def get_form_buttons(self, *args, **kwargs):
        return [CREATE_BUTTON, CHAIN_CREATE_BUTTON, CANCEL_BUTTON]

    def breadcrumb(self):
        return nav.BreadcrumbItem(label=CREATE_BUTTON.title)

    # actions
    def create(self):
        return self.edit()

    chain_create = create

    def cancel(self):
        return self.redirect_to_index()


DELETE_BUTTON = ButtonAction("form", "delete", title=_l("Delete"))


class ObjectDelete[M: ViewedModel, F: Form](ObjectEdit[M, F]):
    """Delete object.

    Supports the DELETE verb.
    """

    methods = ["POST"]
    permission = DELETE
    activity_verb = "delete"
    _message_success = _l("Entity deleted")

    init_object = BaseObjectView.init_object

    def get_form_buttons(self, *args, **kwargs):
        return [DELETE_BUTTON, CANCEL_BUTTON]

    def delete(self):
        session = db.session()
        session.delete(self.obj)
        activity.send(
            self,
            actor=g.user,
            verb="delete",
            object=self.obj,
            target=self.activity_target,
        )
        try:
            session.commit()
        except sa.exc.IntegrityError as e:
            rv = self.handle_commit_exception(e)
            if rv is not None:
                return rv
            session.rollback()
            logger.error(str(e))
            flash(
                _("This entity is referenced by another object and cannot be deleted."),
                "error",
            )
            return self.redirect_to_view()
        else:
            flash(self.message_success(), "success")
            # FIXME: for DELETE verb response in case of success should be 200, 202
            # (accepted) or 204 (no content)
            return self.redirect_to_index()


class JSONBaseSearch(JSONView):
    Model = None
    minimum_input_length = 2

    def __init__(self, *args, **kwargs) -> None:
        Model = kwargs.pop("Model", self.Model)
        minimum_input_length = kwargs.pop(
            "minimum_input_length", self.minimum_input_length
        )
        super().__init__(*args, **kwargs)
        self.Model = Model
        self.minimum_input_length = minimum_input_length

    def prepare_args(self, args, kwargs):
        args, kwargs = super().prepare_args(args, kwargs)
        kwargs["q"] = kwargs.get("q", "").replace("%", " ").lower()
        return args, kwargs

    def data(self, q, *args, **kwargs) -> dict:
        if self.minimum_input_length and len(q) < self.minimum_input_length:
            msg = f"Minimum query length is {self.minimum_input_length:d}"
            raise BadRequest(msg)

        results = []
        for obj in self.get_results(q, **kwargs):
            results.append(self.get_item(obj))

        return {"results": results}

    def get_results(self, q, *args, **kwargs) -> Never:
        raise NotImplementedError

    def get_item(self, obj) -> Never:
        """Return a result item.

        :param obj: Instance object
        :returns: a dictionnary with at least `id` and `text` values
        """
        raise NotImplementedError


class JSONModelSearch(JSONBaseSearch):
    """Base class for json sqlalchemy model search.

    As used by the user pickers for example.
    """

    def get_results(self, q, *args, **kwargs):
        query = self.Model.query

        query = self.options(query)
        query = self.filter(query, q, **kwargs)
        query = self.order_by(query)
        if not q and not self.minimum_input_length:
            query = query.limit(50)
        return query.all()

    def options(self, query):
        return query.options(sa.orm.noload("*"))

    def filter(self, query, q, **kwargs):
        if not q:
            return query
        return query.filter(sa.func.lower(self.Model.name).like(f"{q}%"))

    def order_by(self, query):
        return query.order_by(self.Model.name)

    def get_label(self, obj):
        return obj.name

    def get_item(self, obj):
        """Return a result item.

        :param obj: Instance object
        :returns: a dictionnary with at least `id` and `text` values
        """
        return {"id": obj.id, "text": self.get_label(obj), "name": obj.name}


class JSONWhooshSearch(JSONBaseSearch):
    """Base class for JSON Whoosh search, as used by the user pickers for
    example."""

    def get_results(self, q, *args, **kwargs):
        svc = get_service("indexing")
        search_kwargs = {"limit": 50, "Models": (self.Model,)}
        results = svc.search(q, **search_kwargs)

        itemkey = None
        try:
            # 'nom' doesn't always exist but for Contacts, sorting on
            # the last name ('nom') feels more natural than 'name',
            # which starts with the first name ('prenom').
            if not results.is_empty():
                res = results[0]
                fields = res.fields()
                if "nom" in fields:
                    itemkey = "nom"
                elif "name" in fields:
                    itemkey = "name"
                if itemkey:
                    results.sort(key=lambda it: it.fields().get(itemkey))
        except Exception:
            if itemkey is not None:
                logger.warning(
                    "we could not sort whoosh results on fields' key {itemkey}.",
                    itemkey=itemkey,
                )

        return results

    def get_item(self, hit):
        """Return a result item.

        :param hit: Hit object from Whoosh
        :returns: a dictionnary with at least `id` and `text` values
        """
        return {"id": hit["id"], "text": hit["name"], "name": hit["name"]}
