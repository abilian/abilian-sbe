# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from pathlib import Path

from flask import request, url_for
from flask_login import login_user

from abilian.core.models.subjects import create_root_user
from abilian.services.image import get_format
from abilian.web.preferences.user import UserPreferencesForm

AVATAR_COLORMAP = Path(__file__).parent / "avatar-colormap.png"


def test_form_photo(app, db) -> None:
    user = create_root_user()
    url = url_for("preferences.user")
    uploads = app.extensions["uploads"]
    with AVATAR_COLORMAP.open("rb") as f:
        handle = uploads.add_file(user, f, filename="avatar.png", mimetype="image/png")

    kwargs = {"method": "POST", "data": {"photo": handle}}

    with app.test_request_context(url, **kwargs):
        login_user(user)
        form = UserPreferencesForm(request.form)
        form.validate()
        assert form.photo.data is not None

        img_data = form.photo.data
        # Whatever was uploaded is stored as JPEG.
        assert get_format(img_data) == "JPEG"

        # `photo` is a column, not a relationship: storing it used to fall
        # through into the relationship branch and raise AttributeError.
        form.photo.populate_obj(user, "photo")
        assert user.photo == img_data
