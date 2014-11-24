# coding=utf-8
"""
Celery tasks related to document transformation and preview.
"""
from __future__ import absolute_import

import logging
from guess_language import guessLanguageName

from abilian.services.conversion import ConversionError
from abilian.services import converter
from abilian.core.extensions import celery, db


logger = logging.getLogger(__package__)


@celery.task(ignore_result=True)
def preview_document(document_id):
  """Computes the document preview images with its default preview size.
  """
  from .models import Document

  session = db.create_scoped_session()
  query = session.query(Document)
  document = query.get(document_id)
  if document is None:
    # deleted after task queued, but before task run
    session.close()
    return

  try:
    converter.to_image(document.content_digest, document.content,
                       document.content_type, 0, document.preview_size)
  except ConversionError, e:
    logger.info('Preview failed: %s', str(e),
                exc_info=True, extra={'stack': True})

  session.close()


@celery.task(ignore_result=True)
def convert_document_content(document_id):
  """Converts document content.
  """
  from .models import Document

  session = db.create_scoped_session()
  query = session.query(Document)
  document = query.get(document_id)
  if document is None:
    # deleted after task queued, but before task run
    session.close()
    return

  error_kwargs = dict(exc_info=True, extra={'stack': True})

  conversion_args = (document.content_digest, document.content,
                     document.content_type)

  if document.content_type == "application/pdf":
    document.pdf = document.content
  else:
    try:
      document.pdf = converter.to_pdf(*conversion_args)
    except ConversionError, e:
      document.pdf = ""
      logger.info("Conversion to PDF failed: %s", str(e), **error_kwargs)

  try:
    document.text = converter.to_text(document.content_digest, document.content,
                                      document.content_type)
  except ConversionError, e:
    document.text = u""
    logger.info("Conversion to text failed: %s", str(e), **error_kwargs)

  document.extra_metadata = {}
  try:
    document.extra_metadata = converter.get_metadata(*conversion_args)
  except ConversionError, e:
    logger.warning("Metadata extraction failed: %s", str(e),
                   **error_kwargs)
  except UnicodeDecodeError, e:
    logger.error("Unicode issue: %s", str(e), **error_kwargs)
  except Exception, e:
    logger.error("Other issue: %s", str(e), **error_kwargs)

  if document.text:
    document.language = guessLanguageName(document.text)

  document.page_num = document.extra_metadata.get("PDF:Pages", 1)

  session.commit()
  session.close()

