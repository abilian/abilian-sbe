# Copyright (c) 2012-2024, Abilian SAS

"""`flask antivirus` queues a scan of every document not scanned yet."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dramatiq import Message

from abilian.sbe.apps.documents.cli import antivirus
from abilian.sbe.apps.documents.models import Document, Folder
from abilian.sbe.apps.documents.tasks import antivirus_scan

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from abilian.app import Application


def test_an_unscanned_document_is_queued_for_a_scan(
    app: Application, session: Session
) -> None:
    doc = Document(parent=Folder(title="root"), title="test")
    doc.set_content(b"%PDF-1.4", "application/pdf")
    session.add(doc)
    session.commit()
    # Drop the conversion the commit queued.
    broker = antivirus_scan.broker
    broker.flush_all()

    result = app.test_cli_runner().invoke(antivirus)

    assert result.exit_code == 0, result.output
    queue = broker.queues[antivirus_scan.queue_name].queue
    messages = [Message.decode(data) for data in queue]
    assert [(m.actor_name, m.args) for m in messages] == [
        ("antivirus_scan", (doc.id,))
    ]
