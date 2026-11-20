# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from flask import current_app, flash, g, request
from flask_babel import gettext as _
from werkzeug.exceptions import Forbidden, InternalServerError, NotFound

from abilian.core.signals import activity
from abilian.core.util import unwrap
from abilian.sbe.apps.documents.repository import content_repository
from abilian.services.security import MANAGE, WRITE, is_site_admin
from abilian.web import url_for

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage

    from abilian.core.models.subjects import User
    from abilian.sbe.apps.documents.models import CmisObject, Document, Folder


#
# Utils
#
def breadcrumbs_for(obj: Document) -> list[dict[str, str]]:
    """The folders down to `obj`, then `obj`, each with its page: the pages about
    an object (its permissions, its readers) lead back to it."""
    if obj is None:
        return []

    bc = [{"label": obj.title, "path": url_for(obj)}]
    parent = obj.parent
    while parent and not parent.is_root_folder:
        bc = [{"label": parent.title, "path": url_for(parent)}, *bc]
        parent = parent.parent

    return bc


def get_document(user: User, id: int) -> Document:
    """Gets a document given its id.

    Will raise appropriates errors in case the document doesn't exist in the
    community of the URL (404), or `user` doesn't have read access
    on the document (403).
    """
    doc = content_repository.get_document_by_id(id)
    if doc is None:
        raise NotFound
    check_in_community(doc)
    check_read_access(user, doc)
    return doc


def get_folder(user: User, id: int) -> Folder:
    """Gets a folder given its id.

    Will raise appropriates errors in case the folder doesn't exist in the
    community of the URL (404), or `user` doesn't have read access
    on the folder (403).
    """
    folder = content_repository.get_folder_by_id(id)
    if folder is None:
        raise NotFound
    check_in_community(folder)
    check_read_access(user, folder)
    return folder


def get_new_filename(folder: Folder, name: str) -> str:
    """Given a desired name for a new content in folder, return a name suitable
    for new content.

    If name already exists, a numbered suffix is added.
    """
    existing = {c.name for c in folder.children}
    renamed = name in existing

    if renamed:
        components = name.rsplit(".", 1)
        ext = f".{components[1]}" if len(components) > 1 else ""
        name = components[0]
        prefix = f"{name}-"
        prefix_len = len(prefix)
        # find all numbered suffixes from name-1.ext, name-5.ext,...
        suffixes = (
            n[prefix_len:].rsplit(".", 1)[0]
            for n in existing
            if n.startswith(prefix) and n.endswith(ext)
        )
        int_suffixes = [int(val) for val in suffixes if re.match(r"^\d+$", val)]

        index = max(0, 0, *int_suffixes) + 1  # 0, 0: in case suffixes is empty
        name = f"{name}-{index}{ext}"

    return name


def create_document(user: User, folder: Folder, fs: FileStorage) -> Document:
    check_write_access(user, folder)
    assert isinstance(fs.filename, str)

    name = fs.filename

    if not name:
        msg = "Document name can't be empty."
        flash(_(msg), "error")
        raise ValueError(msg)

    original_name = name
    name = get_new_filename(folder, name)
    doc = folder.create_document(title=name)
    content_type = fs.content_type or ""
    doc.set_content(fs.read(), content_type)

    if original_name != name:
        # set message after document has been successfully created!
        flash(
            _('"{original}" already present in folder, renamed "{name}"').format(
                original=original_name, name=name
            ),
            "info",
        )

    # Some unwrapping before posting event
    app = unwrap(current_app)
    community = g.community._model
    activity.send(app, actor=user, verb="post", object=doc, target=community)

    return doc


def edit_object(obj):
    title = request.form.get("title", "")
    description = request.form.get("description", "")

    changed = False
    if title != obj.title:
        obj.title = title
        changed = True
    if description != obj.description:
        obj.description = description
        changed = True

    return changed


def get_selected_objects(
    user: User, folder: Folder
) -> tuple[list[Folder], list[Document]]:
    """Returns a tuple, (folders, docs), of folders and docs in the specified
    folder that have been selected from the UI."""
    selected_ids = request.form.getlist("object-selected")

    doc_ids = [
        int(x.split(":")[-1]) for x in selected_ids if x.startswith("cmis:document")
    ]
    folder_ids = [
        int(x.split(":")[-1]) for x in selected_ids if x.startswith("cmis:folder")
    ]

    docs = [get_document(user, id) for id in doc_ids]
    folders = [get_folder(user, id) for id in folder_ids]

    for obj in docs + folders:
        if obj.parent != folder:
            raise InternalServerError

    return folders, docs


def check_in_community(obj: CmisObject) -> None:
    """Raise 404 unless `obj` belongs to the community in the URL.

    The document views run under a community's URL: an object from another
    community, or from none (the repository root), is not found there.
    """
    if obj.community is None or obj.community.id != g.community.id:
        raise NotFound


def check_read_access(user: User, obj: CmisObject) -> None:
    """Checks `user` has appropriate read access on the given object.

    Will raise appropriates errors in case the object doesn't exist
    (404), or `user` doesn't have read access on the object
    (403).
    """
    if not obj:
        raise NotFound
    if is_site_admin(user):
        return
    if content_repository.has_access(user, obj):
        return
    raise Forbidden


def check_write_access(user: User, obj: CmisObject) -> None:
    """Checks `user` has appropriate write access on the given
    object.

    Will raise appropriates errors in case the object doesn't exist
    (404), or `user` doesn't have write access on the object
    (403).
    """
    if not obj:
        raise NotFound
    if is_site_admin(user):
        return

    if content_repository.has_access(user, obj) and content_repository.has_permission(
        user, WRITE, obj
    ):
        return
    raise Forbidden


def check_manage_access(user: User, obj: CmisObject) -> None:
    """Checks `user` has appropriate manage access on the given
    object.

    Will raise appropriates errors in case the object doesn't exist
    (404), or `user` doesn't have manage access on the object
    (403).
    """

    if not obj:
        raise NotFound
    if is_site_admin(user):
        return
    if content_repository.has_access(user, obj) and content_repository.has_permission(
        user, MANAGE, obj
    ):
        return
    raise Forbidden


def match(mime_type: str, patterns: tuple[str, str, str]) -> bool:
    if not mime_type:
        mime_type = "application/binary"
    for pat in patterns:
        pat = pat.replace("*", r"\w*")
        if re.match(pat, mime_type):
            return True
    return False
