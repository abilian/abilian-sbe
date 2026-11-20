# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

from pathlib import Path

from pytest import fixture

from abilian.services.image import CROP, SCALE, get_save_format, get_size, resize


@fixture
def orig_image() -> bytes:
    # 725x518
    return (Path(__file__).parent / "cat.jpg").open("rb").read()


def test_get_save_format() -> None:
    assert get_save_format("JPG") == "JPEG"
    assert get_save_format("JPEG") == "JPEG"
    assert get_save_format("PNG") == "PNG"
    assert get_save_format("GIF") == "PNG"
    assert get_save_format("unknown") == "JPEG"


def test_fit(orig_image: bytes) -> None:
    image = resize(orig_image, 500, 500)
    x, y = get_size(image)
    assert (x, y) == (500, 357)

    # image already fits in desired dimension
    image = resize(orig_image, 1000, 1000)
    x, y = get_size(image)
    assert x == 725
    assert y == 518


def test_scale(orig_image: bytes) -> None:
    image = resize(orig_image, 500, 500, SCALE)
    assert get_size(image) == (500, 500)


def test_crop(orig_image: bytes) -> None:
    image = resize(orig_image, 500, 500, CROP)
    assert get_size(image) == (500, 500)
