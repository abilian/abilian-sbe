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
from abilian.services.conversion import ConversionError, HandlerNotFound

logger = logging.getLogger(__package__)


@contextmanager
def get_document(document_id, session=None):
    """Context manager that yields (session, document).
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
    """Run document processing chain.
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
    """Return antivirus.scan() result
    """
    with get_document(document_id) as (session, document):
        if document is None:
            return
        return _run_antivirus(document)


@shared_task
def preview_document(document_id):
    """Compute the document preview images with its default preview size.
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
    """Convert document content.
    """
    with get_document(document_id) as (session, doc):
        if doc is None:
            # deleted after task queued, but before task run
            return

        error_kwargs = dict(exc_info=True, extra={'stack': True})

        conversion_args = (doc.content_digest, doc.content, doc.content_type)

        if doc.content_type == "application/pdf":
            doc.pdf = doc.content
        else:
            try:
                doc.pdf = converter.to_pdf(*conversion_args)
            except HandlerNotFound as e:
                doc.pdf = ""
            except ConversionError as e:
                doc.pdf = ""
                logger.info(u"Conversion to PDF failed for document: %s",
                            doc.name, e, **error_kwargs)

        try:
            doc.text = converter.to_text(doc.content_digest, doc.content,
                                         doc.content_type)
        except ConversionError as e:
            doc.text = u""
            logger.info(u"Conversion to text failed for document %s: %s",
                        doc.name, e, **error_kwargs)

        doc.extra_metadata = {}
        try:
            doc.extra_metadata = converter.get_metadata(*conversion_args)
        except ConversionError as e:
            logger.warning(u"Metadata extraction failed on document %s: %s",
                           doc.name, e, **error_kwargs)
        except UnicodeDecodeError as e:
            logger.error(u"Unicode issue on document %s: %s", doc.name, e,
                         **error_kwargs)
        except Exception as e:
            logger.error(u"Other issue on document %s: %s", doc.name, e,
                         **error_kwargs)

        if doc.text:
            import langid
            doc.language = langid.classify(doc.text)[0]

        doc.page_num = doc.extra_metadata.get("PDF:Pages", 1)
