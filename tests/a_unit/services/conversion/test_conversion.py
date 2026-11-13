# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from warnings import warn

from magic import Magic
from pytest import fixture, mark

from abilian.services.conversion.handler_lock import init_conversion_lock_dir
from abilian.services.conversion.handlers import HAS_LIBREOFFICE, HAS_PDFTOTEXT

if TYPE_CHECKING:
    from collections.abc import Iterator

    from abilian.services.conversion.service import Converter

mime_sniffer = Magic(mime=True)
encoding_sniffer = Magic(mime_encoding=True)

# FIXME: tests that rely on OOo are disabled until we fix stability issues.


@fixture
def converter() -> Iterator[Converter]:
    from abilian.services.conversion import converter as converter_instance

    cache_dir = Path(tempfile.mkdtemp(suffix="unittest"))
    tmp_dir = Path(tempfile.mkdtemp(suffix="unittest"))
    converter_instance.init_work_dirs(cache_dir, tmp_dir)
    # No app here, so ConversionService.init_app() never runs; the handlers take
    # a file lock and need somewhere to put it.
    init_conversion_lock_dir(str(tmp_dir))
    yield converter_instance

    converter_instance.clear()


def read_file(file_name: str) -> bytes:
    return (Path(__file__).parent / "dummy_files" / file_name).read_bytes()


# To text
@mark.skipif(not HAS_PDFTOTEXT, reason="requires poppler or poppler-util")
def test_pdf_to_text(converter: Converter) -> None:
    blob = read_file("onepage.pdf")
    text = converter.to_text("", blob, "application/pdf")
    assert text


@mark.skipif(not HAS_LIBREOFFICE, reason="requires libreoffice")
def test_word_to_text(converter: Converter) -> None:
    blob = read_file("test.doc")
    text = converter.to_text("", blob, "application/msword")
    assert text


@mark.skipif(not HAS_LIBREOFFICE, reason="requires libreoffice")
def test_wordx_to_text(converter: Converter) -> None:
    blob = read_file("test.docx")
    text = converter.to_text("", blob, "application/msword")
    assert text


# def test_excel_to_text(converter):
#     blob = read_file("test.xls")
#     text = converter.to_text("", blob, "application/excel")


# To PDF
@mark.skipif(not HAS_LIBREOFFICE, reason="requires libreoffice")
def test_odt_to_pdf(converter: Converter) -> None:
    blob = read_file("test.odt")
    pdf = converter.to_pdf("", blob, "application/vnd.oasis.opendocument.text")
    assert mime_sniffer.from_buffer(pdf) == "application/pdf"


@mark.skipif(not HAS_LIBREOFFICE, reason="requires libreoffice")
def test_word_to_pdf(converter: Converter) -> None:
    blob = read_file("test.doc")
    pdf = converter.to_pdf("", blob, "application/msword")
    assert mime_sniffer.from_buffer(pdf) == "application/pdf"


@mark.skip("maybe bug due to ImageMagik settings")
def test_image_to_pdf(converter: Converter) -> None:
    blob = read_file("picture.jpg")
    pdf = converter.to_pdf("", blob, "image/jpeg")
    assert mime_sniffer.from_buffer(pdf) == "application/pdf"


# To images
@mark.skipif(not HAS_PDFTOTEXT, reason="requires poppler or poppler-util")
def test_pdf_to_images(converter: Converter) -> None:
    if not os.popen("which pdftoppm").read().strip():
        warn("pdftoppm not found, skipping test")
        return
    blob = read_file("onepage.pdf")
    image = converter.to_image("", blob, "application/pdf", 0)
    assert mime_sniffer.from_buffer(image) == "image/jpeg"


@mark.skipif(
    not HAS_PDFTOTEXT or not HAS_LIBREOFFICE, reason="requires poppler or poppler-util"
)
def test_word_to_images(converter: Converter) -> None:
    blob = read_file("test.doc")
    image = converter.to_image("", blob, "application/msword", 0)
    assert mime_sniffer.from_buffer(image) == "image/jpeg"
