import re
from typing import Dict, List, Tuple

from flask import current_app, flash, g, request
from flask_babel import gettext as _
from flask_login import current_user
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import Forbidden, InternalServerError, NotFound

from abilian.core.signals import activity
from abilian.core.util import unwrap
from abilian.sbe.apps.documents.models import BaseContent, Document, Folder
from abilian.sbe.apps.documents.repository import repository
from abilian.services.security import MANAGE, WRITE, Admin, security
from abilian.web import url_for


#
# Utils
#
def breadcrumbs_for(obj: Document) -> List[Dict[str, str]]:
    if obj is None:
        return []

    bc = [{"label": obj.title}]
    parent = obj.parent
    while parent and not parent.is_root_folder:
        bc = [{"label": parent.title, "path": url_for(parent)}] + bc
        parent = parent.parent

    return bc


def get_document(id: int) -> Document:
    """Gets a document given its id.

    Will raise appropriates errors in case the document doesn't exist
    (404), or the current user doesn't have read access on the document
    (403).
    """
    doc = repository.get_document_by_id(id)
    check_read_access(doc)
    return doc


def get_folder(id: int) -> Folder:
    """Gets a folder given its id.

    Will raise appropriates errors in case the folder doesn't exist
    (404), or the current user doesn't have read access on the folder
    (403).
    """
    folder = repository.get_folder_by_id(id)
    check_read_access(folder)
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


def create_document(folder: Folder, fs: FileStorage) -> Document:
    check_write_access(folder)
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
            _('"{original}" already present in folder, ' 'renamed "{name}"').format(
                original=original_name, name=name
            ),
            "info",
        )

    # Some unwrapping before posting event
    app = unwrap(current_app)
    community = g.community._model
    activity.send(app, actor=current_user, verb="post", object=doc, target=community)

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


def get_selected_objects(folder: Folder) -> Tuple[List[Folder], List[Document]]:
    """Returns a tuple, (folders, docs), of folders and docs in the specified
    folder that have been selected from the UI."""
    selected_ids = request.form.getlist("object-selected")

    doc_ids = [
        int(x.split(":")[-1]) for x in selected_ids if x.startswith("cmis:document")
    ]
    folder_ids = [
        int(x.split(":")[-1]) for x in selected_ids if x.startswith("cmis:folder")
    ]

    docs = list(map(get_document, doc_ids))
    folders = list(map(get_folder, folder_ids))

    for obj in docs + folders:
        if obj.parent != folder:
            raise InternalServerError()

    return folders, docs


def check_read_access(obj: BaseContent) -> bool:
    """Checks the current user has appropriate read access on the given object.

    Will raise appropriates errors in case the object doesn't exist
    (404), or the current user doesn't have read access on the object
    (403).
    """
    if not obj:
        raise NotFound()
    if not security.running:
        return True
    if security.has_role(current_user, Admin):
        return True
    if repository.has_access(current_user, obj):
        return True
    raise Forbidden()


def check_write_access(obj: BaseContent) -> None:
    """Checks the current user has appropriate write access on the given
    object.

    Will raise appropriates errors in case the object doesn't exist
    (404), or the current user doesn't have write access on the object
    (403).
    """
    if not obj:
        raise NotFound()
    if not security.running:
        return
    if security.has_role(current_user, Admin):
        return

    if repository.has_access(current_user, obj) and repository.has_permission(
        current_user, WRITE, obj
    ):
        return
    raise Forbidden()


def check_manage_access(obj):
    """Checks the current user has appropriate manage access on the given
    object.

    Will raise appropriates errors in case the object doesn't exist
    (404), or the current user doesn't have manage access on the object
    (403).
    """

    if not obj:
        raise NotFound()
    if not security.running:
        return
    if security.has_role(current_user, Admin):
        return
    if repository.has_access(current_user, obj) and repository.has_permission(
        current_user, MANAGE, obj
    ):
        return
    raise Forbidden()


def match(mime_type: str, patterns: Tuple[str, str, str]) -> bool:
    if not mime_type:
        mime_type = "application/binary"
    for pat in patterns:
        pat = pat.replace("*", r"\w*")
        if re.match(pat, mime_type):
            return True
    return False
