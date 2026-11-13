# Copyright (c) 2012-2024, Abilian SAS

"""The check shared by the community image and the user photo uploads."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage
from wtforms.validators import ValidationError

from abilian.web.forms.validators import open_png_or_jpeg


def _upload(filename: str, fmt: str | None) -> FileStorage:
    stream = BytesIO()
    if fmt:
        Image.new("RGB", (4, 4), "red").save(stream, fmt)
    else:
        stream.write(b"not an image")
    stream.seek(0)
    return FileStorage(stream, filename=filename)


@pytest.mark.parametrize(
    ("filename", "fmt"), [("me.png", "PNG"), ("me.JPG", "JPEG"), ("me.jpeg", "JPEG")]
)
def test_a_png_or_jpeg_is_accepted_and_left_readable(filename: str, fmt: str) -> None:
    upload = _upload(filename, fmt)

    image = open_png_or_jpeg(upload)

    assert image.format == fmt
    assert upload.stream.tell() == 0


@pytest.mark.parametrize(
    ("filename", "fmt"),
    [
        ("me.gif", "GIF"),  # by name
        ("me.png", "GIF"),  # by content, whatever the name says
        ("me.png", None),  # not an image at all
        ("", "PNG"),  # no name
    ],
)
def test_anything_else_is_refused(filename: str, fmt: str | None) -> None:
    with pytest.raises(ValidationError):
        open_png_or_jpeg(_upload(filename, fmt))
