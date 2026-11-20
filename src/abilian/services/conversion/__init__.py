# Copyright (c) 2012-2024, Abilian SAS

"""Conversion service.

Hardcoded to manage only conversion to PDF, to text and to image series.

Includes result caching (on filesystem).

Assumes poppler-utils and LibreOffice are installed.

TODO: rename Converter into ConversionService ?
"""

from __future__ import annotations

from abilian.services.conversion.handlers import (
    ImageMagickHandler,
    LibreOfficePdfHandler,
    PdfToPpmHandler,
    PdfToTextHandler,
)

from .exceptions import ConversionError
from .service import Converter, HandlerNotFoundError

# Singleton, yuck!
converter = Converter()
converter.register_handler(PdfToTextHandler())
converter.register_handler(PdfToPpmHandler())
converter.register_handler(ImageMagickHandler())
converter.register_handler(LibreOfficePdfHandler())

conversion_service = converter

__all__ = (
    "ConversionError",
    "Converter",
    "HandlerNotFoundError",
    "conversion_service",
    "converter",
)
