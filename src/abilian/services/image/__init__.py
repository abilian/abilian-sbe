# Copyright (c) 2012-2024, Abilian SAS

"""Provides tools (currently: only functions, not a real service) for image
processing."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image

__all__ = ["CROP", "FIT", "RESIZE_MODES", "SCALE", "get_format", "resize"]

# resize modes

#: resize without retaining original proportions
SCALE = "scale"

#: resize image and retain original proportions. Image width and height will be
#: at most specified width and height, respectively; At least width or height
#: will be equal to specified width and height, respectively.
FIT = "fit"

#: crop image and resize so that it matches specified width and height.
CROP = "crop"

RESIZE_MODES = frozenset({SCALE, FIT, CROP})


def open_image(img: BytesIO | bytes) -> Image.Image:
    if isinstance(img, bytes):
        img = BytesIO(img)

    pos = img.tell()
    image = Image.open(img)
    img.seek(pos)
    return image


def get_format(img):
    if not img:
        raise OSError
    image = open_image(img)
    return image.format


def get_size(img: bytes) -> tuple[int, int]:
    image = open_image(img)
    return image.size


def get_save_format(fmt: str) -> str:
    if fmt in ("GIF", "PNG"):
        return "PNG"
    return "JPEG"


def resize(orig: BytesIO | bytes, width: int, height: int, mode: str = FIT) -> bytes:
    """Return `orig` resized to `width` x `height`, following `mode`.

    Not cached: a cache would hold each original, a converted document's pages
    among them, in every process; the responses are cached by the browsers.
    """
    data = orig if isinstance(orig, bytes) else orig.read()
    image = open_image(data)
    image_format = image.format
    x, y = image.size

    if (x, y) == (width, height):
        return data

    if mode == SCALE:
        image = image.resize((width, height), Image.LANCZOS)
        assert image.size == (width, height)
    elif mode == FIT:
        if x >= width or y >= height:
            # resize only if images exceed desired dimensions
            image.thumbnail((width, height), Image.LANCZOS)
            x1, y1 = image.size
            assert x1 == width or y1 == height
    elif mode == CROP:
        image = _crop_and_resize(image, width, height)
        assert image.size == (width, height)

    output = BytesIO()
    image.save(output, get_save_format(image_format))
    return output.getvalue()


def _crop_and_resize(image: Image.Image, width: int, height: int = 0) -> Image.Image:
    if not height:
        height = width

    # Compute cropping coordinates
    x0, y0 = image.size

    w_ratio = 1.0 * x0 / width
    h_ratio = 1.0 * y0 / height

    if h_ratio > w_ratio:
        x1 = 0
        x2 = x0
        y1 = int((y0 - x0 * height / width) / 2)
        y2 = int((y0 + x0 * height / width) / 2)
    else:
        x1 = int((x0 - y0 * width / height) / 2)
        x2 = int((x0 + y0 * width / height) / 2)
        y1 = 0
        y2 = y0

    image = image.crop((x1, y1, x2, y2))
    # image.load()
    image = image.resize((width, height), Image.LANCZOS)
    return image
