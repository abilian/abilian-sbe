# coding=utf-8
"""
Celery tasks related to document transformation and preview.
"""
from __future__ import absolute_import

import logging
from contextlib import contextmanager

from celery import shared_task

from abilian.core.extensions import db
from abilian.services import converter, get_service
from abilian.services.conversion import ConversionError

logger = logging.getLogger(__package__)


@contextmanager
def get_document(document_id, session=None):
    """ Context manager that yields (session, document).
    """
    from .models import Document

    doc_session = session
    if session is None:
        doc_session = db.create_scoped_session()

    with doc_session.begin_nested():
        query = doc_session.query(Document)
        document = query.get(document_id)
        yield (doc_session, document)

    # cleanup
    if session is None:
        doc_session.commit()
        doc_session.close()


@shared_task
def process_document(document_id):
    """ Run document processing chain.
    """
    with get_document(document_id) as (session, document):
        if document is None:
            return

        # True = Ok, None means no check performed (no antivirus present)
        is_clean = _run_antivirus(document)
        if is_clean is False:
            return

    preview_document.delay(document_id)
    convert_document_content.delay(document_id)


def _run_antivirus(document):
    antivirus = get_service('antivirus')
    if antivirus and antivirus.running:
        is_clean = antivirus.scan(document.content_blob)
        if 'antivirus_task' in document.content_blob.meta:
            del document.content_blob.meta['antivirus_task']
        return is_clean
    return None


@shared_task
def antivirus_scan(document_id):
    """ Return antivirus.scan() result
    """
    with get_document(document_id) as (session, document):
        if document is None:
            return
        return _run_antivirus(document)


@shared_task
def preview_document(document_id):
    """ Compute the document preview images with its default preview size.
    """
    with get_document(document_id) as (session, document):
        if document is None:
            # deleted after task queued, but before task run
            return

        try:
            converter.to_image(document.content_digest, document.content,
                               document.content_type, 0, document.preview_size)
        except ConversionError as e:
            logger.info('Preview failed: %s',
                        str(e),
                        exc_info=True,
                        extra={'stack': True})


@shared_task
def convert_document_content(document_id):
    """ Convert document content.
    """
    with get_document(document_id) as (session, document):
        if document is None:
            # deleted after task queued, but before task run
            return

        error_kwargs = dict(exc_info=True, extra={'stack': True})

        conversion_args = (document.content_digest, document.content,
                           document.content_type)

        if document.content_type == "application/pdf":
            document.pdf = document.content
        else:
            try:
                document.pdf = converter.to_pdf(*conversion_args)
            except ConversionError as e:
                document.pdf = ""
                logger.info("Conversion to PDF failed: %s", str(e),
                            **error_kwargs)

        try:
            document.text = converter.to_text(document.content_digest,
                                              document.content,
                                              document.content_type)
        except ConversionError as e:
            document.text = u""
            logger.info("Conversion to text failed: %s", str(e), **error_kwargs)

        document.extra_metadata = {}
        try:
            document.extra_metadata = converter.get_metadata(*conversion_args)
        except ConversionError as e:
            logger.warning("Metadata extraction failed: %s", str(e),
                           **error_kwargs)
        except UnicodeDecodeError as e:
            logger.error("Unicode issue: %s", str(e), **error_kwargs)
        except Exception as e:
            logger.error("Other issue: %s", str(e), **error_kwargs)

        if document.text:
            import langid
            document.language = langid.classify(document.text)[0]

        document.page_num = document.extra_metadata.get("PDF:Pages", 1)
