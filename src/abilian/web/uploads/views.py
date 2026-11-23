# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import typing

from flask import current_app, send_file
from flask_wtf.file import FileField, file_required
from werkzeug.exceptions import BadRequest, NotFound
from werkzeug.utils import secure_filename

from abilian.core.extensions.login import authenticated_user
from abilian.services.security import AUTHENTICATED
from abilian.web import url_for
from abilian.web.access_blueprint import AccessControlBlueprint
from abilian.web.forms import Form
from abilian.web.views import JSONView, View

if typing.TYPE_CHECKING:
    from abilian.core.models.subjects import User
    from abilian.web.uploads import FileUploadsExtension


ac_blueprint = AccessControlBlueprint(
    "uploads", __name__, url_prefix="/upload", allowed_roles=AUTHENTICATED
)


class UploadForm(Form):
    file = FileField(validators=(file_required(),))


class BaseUploadsView:
    uploads: FileUploadsExtension
    user: User

    def prepare_args(self, args, kwargs):
        args, kwargs = super().prepare_args(args, kwargs)
        self.uploads = current_app.extensions["uploads"]
        self.user = authenticated_user()
        return args, kwargs


class NewUploadView(BaseUploadsView, JSONView):
    """Upload a new file."""

    methods = ["POST", "PUT"]

    #: file handle to be returned
    handle = None

    def data(self, *args, **kwargs) -> dict:
        return {"handle": self.handle, "url": url_for(".handle", handle=self.handle)}

    def post(self, *args, **kwargs):
        form = UploadForm()

        if not form.validate():
            msg = "File is missing."
            raise BadRequest(msg)

        uploaded = form["file"].data
        filename = secure_filename(uploaded.filename)
        mimetype = uploaded.mimetype
        self.handle = self.uploads.add_file(
            self.user, uploaded, filename=filename, mimetype=mimetype
        )
        return self.get(*args, **kwargs)

    def put(self, *args, **kwargs):
        return self.post(*args, **kwargs)


ac_blueprint.add_url_rule("/", view_func=NewUploadView.as_view("new_file"))


class UploadView(BaseUploadsView, View):
    """Manage an uploaded file: download, delete."""

    methods = ["GET", "DELETE"]

    def get(self, handle, *args, **kwargs):
        file_obj = self.uploads.get_file(self.user, handle)

        if file_obj is None:
            raise NotFound

        metadata = self.uploads.get_metadata(self.user, handle)
        filename = metadata.get("filename", handle)
        content_type = metadata.get("mimetype")
        stream = file_obj.open("rb")

        return send_file(
            stream,
            as_attachment=True,
            download_name=filename,
            mimetype=content_type,
            max_age=0,
            etag=False,
        )

    def delete(self, handle, *args, **kwargs) -> dict:
        if self.uploads.get_file(self.user, handle) is None:
            raise NotFound
        self.uploads.remove_file(self.user, handle)
        return {"success": True}


ac_blueprint.add_url_rule("/<string:handle>", view_func=UploadView.as_view("handle"))
