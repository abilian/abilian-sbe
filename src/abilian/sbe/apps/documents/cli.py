import click
import sqlalchemy as sa
import sqlalchemy.orm
from flask.cli import with_appcontext

from . import tasks
from .models import Document


@click.command()
@with_appcontext
def antivirus():
    """Schedule documents to antivirus scan."""

    documents = Document.query.filter(Document.content_blob != None).options(
        sa.orm.noload("creator"),
        sa.orm.noload("owner"),
        sa.orm.joinedload("content_blob"),
    )

    total = 0
    count = 0
    for d in documents.yield_per(1000):
        total += 1
        meta = d.content_blob.meta
        if "antivirus" not in meta and "antivirus_task" not in meta:
            tasks.antivirus_scan.delay(d.id)
            count += 1

    print(f"{count}/{total} documents scheduled")
