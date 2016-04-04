import re

from flask import current_app, flash, g, request
from flask_babel import gettext as _
from werkzeug.exceptions import Forbidden, InternalServerError, NotFound

from abilian.core.signals import activity
from abilian.services.security import MANAGE, WRITE, Admin, security
from abilian.web import url_for

from ..repository import repository


#
# Utils
#
def breadcrumbs_for(object):
    if object is None:
        return []

    bc = [dict(label=object.title)]
    parent = object.parent
    while parent and not parent.is_root_folder:
        bc = [dict(label=parent.title, path=url_for(parent))] + bc
        parent = parent.parent

    return bc


def get_document(id):
    """
    Gets a document given its id. Will raise appropriates errors in case
    the document doesn't exist (404), or the current user doesn't have read access
    on the document (403).
    """
    doc = repository.get_document_by_id(id)
    check_read_access(doc)
    return doc


def get_folder(id):
    """
    Gets a folder given its id. Will raise appropriates errors in case
    the folder doesn't exist (404), or the current user doesn't have read access
    on the folder (403).
    """
    folder = repository.get_folder_by_id(id)
    check_read_access(folder)
    return folder


def get_new_filename(folder, name):
    """
    Given a desired name for a new content in folder, return a name suitable
    for new content.

    If name already exists, a numbered suffix is added.
    """
    existing = set((c.name for c in folder.children))
    renamed = name in existing

    if renamed:
        name = name.rsplit('.', 1)
        ext = u'.{}'.format(name[1]) if len(name) > 1 else u''
        name = name[0]
        prefix = u'{}-'.format(name)
        prefix_len = len(prefix)
        # find all numbered suffixes from name-1.ext, name-5.ext,...
        suffixes = (n[prefix_len:].rsplit(u'.', 1)[0]
                    for n in existing
                    if n.startswith(prefix) and n.endswith(ext))
        suffixes = [int(val) for val in suffixes if re.match(r'^\d+$', val)]

        index = max(0, 0, *suffixes) + 1  # 0, 0: in case suffixes is empty
        name = u'{}-{}{}'.format(name, index, ext)

    return name


def create_document(folder, fs):
    check_write_access(folder)

    if isinstance(fs.filename, unicode):
        name = fs.filename
    else:
        name = unicode(fs.filename, errors='ignore')

    if not name:
        flash(_(u"Document name can't be empty."), "error")
        return None

    original_name = name
    name = get_new_filename(folder, name)
    doc = folder.create_document(title=name)
    doc.set_content(fs.read(), fs.content_type)

    if original_name != name:
        # set message after document has been successfully created!
        flash(_(u'"{original}" already present in folder, '
                'renamed "{name}"').format(original=original_name, name=name),
              'info')

    # Some unwrapping before posting event
    app = current_app._get_current_object()
    community = g.community._model
    activity.send(app, actor=g.user, verb="post", object=doc, target=community)

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


def get_selected_objects(folder):
    """
    Returns a tuple, (folders, docs), of folders and docs in the specified
    folder that have been selected from the UI.
    """
    selected_ids = request.form.getlist("object-selected")

    doc_ids = [int(x.split(":")[-1])
               for x in selected_ids if x.startswith("cmis:document")]
    folder_ids = [int(x.split(":")[-1])
                  for x in selected_ids if x.startswith("cmis:folder")]

    docs = map(get_document, doc_ids)
    folders = map(get_folder, folder_ids)

    for obj in docs + folders:
        if obj.parent != folder:
            raise InternalServerError()

    return folders, docs


def check_read_access(obj):
    """
    Checks the current user has appropriate read access on the given object.
    Will raise appropriates errors in case the object doesn't exist (404),
    or the current user doesn't have read access on the object (403).
    """
    if not obj:
        raise NotFound()
    if not security.running:
        return True
    if security.has_role(g.user, Admin):
        return True
    if repository.has_access(g.user, obj):
        return True
    raise Forbidden()


def check_write_access(obj):
    """
    Checks the current user has appropriate write access on the given object.
    Will raise appropriates errors in case the object doesn't exist (404),
    or the current user doesn't have write access on the object (403).
    """
    if not obj:
        raise NotFound()
    if not security.running:
        return
    if security.has_role(g.user, Admin):
        return

    if (repository.has_access(g.user, obj) and
            repository.has_permission(g.user, WRITE, obj)):
        return
    raise Forbidden()


def check_manage_access(obj):
    """
    Checks the current user has appropriate manage access on the given object.
    Will raise appropriates errors in case the object doesn't exist (404),
    or the current user doesn't have manage access on the object (403).
    """

    if not obj:
        raise NotFound()
    if not security.running:
        return
    if security.has_role(g.user, Admin):
        return
    if (repository.has_access(g.user, obj) and
            repository.has_permission(g.user, MANAGE, obj)):
        return
    raise Forbidden()


def match(mime_type, patterns):
    if not mime_type:
        mime_type = "application/binary"
    for pat in patterns:
        pat = pat.replace("*", r"\w*")
        if re.match(pat, mime_type):
            return True
    return False
