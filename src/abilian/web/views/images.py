# Copyright (c) 2012-2024, Abilian SAS

"""Blueprint for views of dynamic images."""

from __future__ import annotations

import colorsys
import hashlib
import zlib
from importlib import resources as rso
from pathlib import Path
from typing import Any

import sqlalchemy as sa
import sqlalchemy.orm
from flask import make_response, render_template, request
from werkzeug.exceptions import BadRequest, NotFound

from abilian.core.models.blob import Blob
from abilian.core.models.subjects import User
from abilian.services.image import CROP, RESIZE_MODES, get_format, get_size, resize
from abilian.services.security import AUTHENTICATED
from abilian.web.access_blueprint import AccessControlBlueprint
from abilian.web.util import url_for

from .files import BaseFileDownload

images_bp = AccessControlBlueprint(
    "images", __name__, url_prefix="/images", allowed_roles=AUTHENTICATED
)
route = images_bp.route

DEFAULT_AVATAR = rso.files("abilian.web") / "resources" / "img" / "avatar-default.png"
DEFAULT_AVATAR_MD5 = hashlib.md5(DEFAULT_AVATAR.read_bytes()).hexdigest()  # noqa: S324


class BaseImageView(BaseFileDownload):
    max_size = None

    def __init__(self, max_size=None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Override class default value only if arg is specified in constructor.
        # This allows subclasses to easily override theses defaults.
        if max_size is not None:
            self.max_size = max_size

    def prepare_args(self, args, kwargs):
        args, kwargs = super().prepare_args(args, kwargs)
        size = request.args.get("s", 0)
        try:
            size = int(size)
        except ValueError as e:
            msg = f'Invalid value for "s": {size:d}. Not an integer.'
            raise BadRequest(msg) from e

        if self.max_size is not None and size > self.max_size:
            msg = f"Size too large: {size:d} (max: {self.max_size:d})"
            raise BadRequest(msg)

        kwargs["size"] = size

        resize_mode = request.args.get("m", CROP)
        if resize_mode not in RESIZE_MODES:
            resize_mode = CROP

        kwargs["mode"] = resize_mode
        return args, kwargs

    def make_response(self, image, size, mode, filename=None, *args, **kwargs):
        """
        :param image: image as bytes
        :param size: requested maximum width/height size
        :param mode: one of 'scale', 'fit' or 'crop'
        :param filename: filename
        """
        try:
            fmt = get_format(image)
        except OSError as e:
            # not a known image file
            raise NotFound from e

        self.content_type = "image/png" if fmt == "PNG" else "image/jpeg"
        ext = f".{fmt.lower()!s}"

        if not filename:
            filename = "image"
        if not filename.lower().endswith(ext):
            filename += ext
        self.filename = filename

        if size:
            image = resize(image, size, size, mode=mode)
            if mode == CROP:
                assert get_size(image) == (size, size)
        else:
            image = image.read()

        return make_response(image)

    def get_filename(self, *args, **kwargs):
        return self.filename

    def get_content_type(self, *args, **kwargs):
        return self.content_type


class StaticImageView(BaseImageView):
    """View for static assets not served by static directory.

    Useful for default avatars for example.
    """

    expire_vary_arg = "md5"

    def __init__(self, image, *args, **kwargs) -> None:
        """
        :param image: path to image file
        """
        super().__init__(*args, **kwargs)
        self.image_path = Path(image)
        if not self.image_path.exists():
            p = str(self.image_path)
            msg = f"Invalid image path: {p!r}"
            raise ValueError(msg)

    def prepare_args(self, args, kwargs):
        kwargs["image"] = self.image_path.open("rb")
        kwargs["filename"] = self.image_path.name
        return super().prepare_args(args, kwargs)


class BlobView(BaseImageView):
    """Default :attr:`expire_vary_arg` to `"md5"`.

    :attr:`set_expire` is set to `False` by default.
    """

    expire_vary_arg = "md5"
    id_arg = "object_id"

    def __init__(self, id_arg=None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if id_arg is not None:
            self.id_arg = id_arg

    def prepare_args(self, args, kwargs):
        args, kwargs = super().prepare_args(args, kwargs)
        blob_id = kwargs.get(self.id_arg)
        try:
            blob_id = int(blob_id)
        except ValueError as e:
            msg = f"Invalid blob id: {blob_id!r}"
            raise BadRequest(msg) from e

        blob = Blob.query.get(blob_id)
        if not blob:
            raise NotFound

        meta = blob.meta
        filename = meta.get("filename", meta.get("md5", str(blob.uuid)))
        kwargs["filename"] = filename
        kwargs["image"] = blob.file.open("rb")
        return args, kwargs


class UserMugshot(BaseImageView):
    expire_vary_arg = "md5"

    def prepare_args(self, args, kwargs):
        args, kwargs = super().prepare_args(args, kwargs)

        user_id = kwargs["user_id"]
        user = User.query.options(sa.orm.undefer(User.photo)).get(user_id)

        if user is None:
            raise NotFound

        kwargs["user"] = user
        kwargs["image"] = user.photo
        return args, kwargs

    def make_response(self, user, image, size, *args, **kwargs):
        if image:
            # user has set a photo
            return super().make_response(image, size, *args, **kwargs)

        # render svg avatar
        if user.last_name:
            letter = user.last_name[0]
        elif user.first_name:
            letter = user.first_name[0]
        else:
            letter = "?"
        letter = letter.upper()
        color = avatar_color(user.name, user.email)
        svg = render_template(
            "default/avatar.svg", color=color, letter=letter, size=size
        )
        response = make_response(svg)
        self.content_type = "image/svg+xml"
        self.filename = f"avatar-{_avatar_key(user.name, user.email)}.svg"
        return response


def avatar_color(name: str, email: str) -> str:
    """One of ten pastel colours (65% saturation), fixed for a given user."""
    hue = (_avatar_key(name, email) % 10) * 36 / 360.0
    red, green, blue = (int(x * 255) for x in colorsys.hsv_to_rgb(hue, 0.65, 1.0))
    return f"rgb({red}, {green}, {blue})"


def _avatar_key(name: str, email: str) -> int:
    # Not `hash()`: Python salts it per process, so the colour changed on every
    # restart and between workers.
    return zlib.crc32((name + email).encode("utf-8"))


user_photo = UserMugshot.as_view("user_photo", set_expire=True, max_size=500)
route("/users/<int:user_id>")(user_photo)
route("/users/default")(
    StaticImageView.as_view("user_default", set_expire=True, image=DEFAULT_AVATAR)
)


def user_url_args(user: User | None, size: int) -> tuple[str, dict[str, Any]]:
    endpoint = "images.user_default"
    kwargs = {"s": size, "md5": DEFAULT_AVATAR_MD5}

    # `None` is a real state, not a caller's mistake: AuditEntry.user_id is
    # nullable, so an action taken outside a request -- a migration, the CLI,
    # create_root_user -- has no acting user. The default avatar is exactly
    # what it should get; the admin audit panel used to crash on it.
    if user is not None:
        endpoint = "images.user_photo"
        kwargs["user_id"] = user.id
        content = user.photo or (user.name + user.email).encode("utf-8")
        kwargs["md5"] = hashlib.md5(content).hexdigest()  # noqa: S324

    return endpoint, kwargs


def user_photo_url(user, size):
    """Return url to use for this user."""
    endpoint, kwargs = user_url_args(user, size)
    return url_for(endpoint, **kwargs)
