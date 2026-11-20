# Copyright (c) 2026, Abilian SAS

"""The files of a wiki page or an event, attached and removed from its form when it
is saved: new ones in the `attachments` field, those to remove ticked as
`remove_attachment` (`ads_macros.files_field`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import request

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from werkzeug.datastructures import FileStorage

    from .models import BaseContent


def attach_files(
    attachments: list, files: Iterable[FileStorage], make: Callable[..., BaseContent]
) -> int:
    """Add `files` to `attachments`, each made by `make`; how many there were. A
    file field left empty sends a file with no name, which is not one."""
    named = [f for f in files if f.filename]
    for f in named:
        attachment = make(name=f.filename)
        attachment.set_content(f.read(), f.content_type)
        attachments.append(attachment)
    return len(named)


def apply_form_files(attachments: list, make: Callable[..., BaseContent]) -> None:
    """What the form asked of the files: new ones attached, and those ticked taken
    off, among `attachments` only, whatever ids were posted."""
    attach_files(attachments, request.files.getlist("attachments"), make)
    removed = set(request.form.getlist("remove_attachment", type=int))
    for attachment in [a for a in attachments if a.id in removed]:
        attachments.remove(attachment)


def form_touches_files() -> bool:
    """Whether the form attached or removed any file."""
    attached = any(f.filename for f in request.files.getlist("attachments"))
    return attached or bool(request.form.getlist("remove_attachment"))
