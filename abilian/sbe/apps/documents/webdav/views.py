import os.path
import uuid

from flask import Blueprint, request
from flask_login import current_user
from lxml.etree import XMLSyntaxError
from werkzeug.datastructures import Headers
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.wrappers import BaseResponse as Response

from abilian.core.extensions import db
from abilian.services import get_service

from .. import repository
from .constants import DAV_PROPS, HTTP_BAD_REQUEST, HTTP_CONFLICT, \
    HTTP_CREATED, HTTP_METHOD_NOT_ALLOWED, HTTP_MULTI_STATUS, \
    HTTP_NO_CONTENT, HTTP_OK, HTTP_PRECONDITION_FAILED, OPTIONS
from .xml import MultiStatus, Propfind

webdav = Blueprint("webdav", __name__, url_prefix="/webdav")
route = webdav.route

__all__ = ["webdav"]

#
# Utils
#


# TODO: real logging
class Logger:
    def debug(self, msg):
        print(msg)


log = Logger()


# XXX: temporary debug info.
@webdav.before_request
def log_request():
    litmus_msg = request.headers.get("X-Litmus")
    if litmus_msg:
        print("")
        print(78 * "#")
        print(litmus_msg)
        print(f"{request.method} on {request.path}")


@webdav.before_request
def only_admin():
    security = get_service("security")

    if not security.has_role(current_user, "admin"):
        raise Forbidden()


@webdav.after_request
def log_response(response):
    print(f"Response: {response}")
    return response


def normpath(path):
    path = os.path.normpath(path)
    if not path.startswith("/"):
        path = "/" + path
    return path


def split_path(path):
    path = normpath(path)
    return os.path.dirname(path), os.path.basename(path)


def get_object(path):
    obj = repository.get_object_by_path(path)
    if obj is None:
        raise NotFound()
    return obj


@webdav.before_app_request
def create_root_folder():
    # TODO: create root folder on repository startup instead.
    # assert repository.root_folder
    pass


#
# HTTP endpoints
#
@route("/", methods=["OPTIONS"], defaults={"path": "/"})
@route("/<path:path>", methods=["OPTIONS"])
def options(path):
    headers = {
        "Content-Type": "text/plain",
        "Content-Length": "0",
        "DAV": "1,2",
        "MS-Author-Via": "DAV",
        "Allow": OPTIONS,
    }
    print("Returning", headers)
    return "", HTTP_OK, headers


@route("/", defaults={"path": "/"})
@route("/<path:path>")
def get(path):
    path = normpath(path)

    obj = get_object(path)

    file_name = obj.file_name.encode("utf8")
    headers = {
        "Content-Type": obj.content_type,
        "Content-Disposition": f"attachment;filename={file_name}",
    }
    return obj.content, HTTP_OK, headers


@route("/<path:path>", methods=["MKCOL"])
def mkcol(path):
    path = normpath(path)
    parent_path, name = split_path(path)

    if request.data:
        return "Request body must be empty.", 415, {}

    obj = repository.get_object_by_path(path)
    if obj is not None:
        return "Objet already exists.", HTTP_METHOD_NOT_ALLOWED, {}

    parent_folder = repository.get_folder_by_path(parent_path)
    if parent_folder is None:
        return "Parent collection doesn't exist.", HTTP_CONFLICT, {}

    new_folder = parent_folder.create_subfolder(name=name)  # noqa
    db.session.commit()
    return "", HTTP_CREATED, {}


@route("/<path:path>", methods=["PUT"])
def put(path):
    path = normpath(path)
    parent_path, name = split_path(path)

    status = HTTP_CREATED
    obj = repository.get_object_by_path(path)
    if obj is not None:
        if not obj.is_document:
            return "", HTTP_METHOD_NOT_ALLOWED, {}
        else:
            status = HTTP_NO_CONTENT
    else:
        parent_folder = repository.get_folder_by_path(parent_path)
        if parent_folder is None:
            return "", HTTP_CONFLICT, {}
        obj = parent_folder.create_document(name=name)

    obj.content = request.data
    obj.content_type = request.content_type

    db.session.commit()
    return "", status, {}


@route("/<path:path>", methods=["DELETE"])
def delete(path):
    path = normpath(path)

    obj = get_object(path)

    db.session.delete(obj)
    db.session.commit()
    return "", HTTP_NO_CONTENT, {}


@route("/<path:path>", methods=["COPY", "MOVE"])
def copy_or_move(path):
    path = normpath(path)
    dest = request.headers.get("destination")
    dest_path = normpath(dest[len(request.url_root + "webdav") :])
    dest_parent_path, dest_name = split_path(dest_path)
    overwrite = request.headers.get("overwrite")

    orig_obj = get_object(path)

    status = HTTP_CREATED
    dest_obj = repository.get_object_by_path(dest_path)
    if dest_obj:
        if overwrite == "F":
            return "", HTTP_PRECONDITION_FAILED, {}
        else:
            repository.delete_object(dest_obj)
            db.session.flush()
            status = HTTP_NO_CONTENT

    dest_folder = repository.get_folder_by_path(dest_parent_path)
    if dest_folder is None:
        return "", HTTP_CONFLICT, {}

    if request.method == "COPY":
        repository.copy_object(orig_obj, dest_folder, dest_name)
    else:
        if dest_folder == orig_obj.parent:
            repository.rename_object(orig_obj, dest_name)
        else:
            repository.move_object(orig_obj, dest_folder, dest_name)

    db.session.commit()
    return "", status, {}


@route("/", defaults={"path": "/"}, methods=["PROPFIND"])
@route("/<path:path>", methods=["PROPFIND"])
def propfind(path):
    path = normpath(path)
    depth = request.headers.get("depth", "1")

    print(request.headers)
    print(request.data)

    try:
        propfind = Propfind(request.data)  # noqa
    except XMLSyntaxError:
        return "Malformed XML document.", HTTP_BAD_REQUEST, {}

    obj = get_object(path)

    m = MultiStatus()
    m.add_response_for(request.url, obj, DAV_PROPS)

    if depth == "1" and obj.is_folder:
        for child in obj.children:
            m.add_response_for(request.url + "/" + child.name, child, DAV_PROPS)

    print(m.to_string())

    headers = {"Content-Type": "text/xml"}
    return m.to_string(), HTTP_MULTI_STATUS, headers


@route("/<path:path>", methods=["LOCK"])
def lock(path):
    path = normpath(path)
    obj = get_object(path)
    token = str(uuid.uuid1())

    if repository.is_locked(obj):
        if not repository.can_unlock(obj):
            return "", 423, {}
        else:
            headers = {"Lock-Token": "urn:uuid:" + token}
            return "TODO", HTTP_OK, headers

    token = repository.lock(obj)

    xml = f"""<?xml version="1.0" encoding="utf-8" ?>
<D:prop xmlns:D="DAV:">
    <D:lockdiscovery>
        <D:activelock>
            <D:lockscope><D:exclusive/></D:lockscope>
            <D:locktype><D:write/></D:locktype>
            <D:depth>0</D:depth>
            <D:timeout>Second-179</D:timeout>
            <D:owner>flora</D:owner>
            <D:locktoken>
                <D:href>opaquelocktoken:{token}</D:href>
            </D:locktoken>
        </D:activelock>
    </D:lockdiscovery>
</D:prop>"""

    hlist = [("Content-Type", "text/xml"), ("Lock-Token", f"<urn:uuid:{token}>")]

    return Response(xml, headers=Headers.linked(hlist))  # , status ='423 Locked'
    # public Response lock(@Context UriInfo uriInfo) throws Exception {
    #     String token = null;
    #     Prop prop = null;
    #     if (backend.isLocked(doc.getRef())) {
    #         if (!backend.canUnlock(doc.getRef())) {
    #             return Response.status(423).build();
    #         } else {
    #             token = backend.getCheckoutUser(doc.getRef());
    #             prop = new Prop(getLockDiscovery(doc, uriInfo));
    #             return Response.ok().entity(prop).header("Lock-Token",
    #                     "urn:uuid:" + token).build();
    #         }
    #     }
    #
    #     token = backend.lock(doc.getRef());
    #     if (READONLY_TOKEN.equals(token)) {
    #         return Response.status(423).build();
    #     } else if (StringUtils.isEmpty(token)) {
    #         return Response.status(400).build();
    #     }
    #
    #     prop = new Prop(getLockDiscovery(doc, uriInfo));
    #
    #     backend.saveChanges();
    #     return Response.ok().entity(prop).header("Lock-Token",
    #             "urn:uuid:" + token).build();
    # }


@route("/<path:path>", methods=["UNLOCK"])
def unlock(path):
    path = normpath(path)
    obj = get_object(path)

    if repository.is_locked(obj):
        if not repository.can_unlock(obj):
            return "", 423, {}
        else:
            repository.unlock(obj)
            db.session.commit()
            return "", HTTP_NO_CONTENT, {}

    return "", HTTP_NO_CONTENT, {}
    #     if (backend.isLocked(doc.getRef())) {
    #         if (!backend.canUnlock(doc.getRef())) {
    #             return Response.status(423).build();
    #         } else {
    #             backend.unlock(doc.getRef());
    #             backend.saveChanges();
    #             return Response.status(HTTP_NO_CONTENT).build();
    #         }
    #     } else {
    #         // TODO: return an error
    #         return Response.status(HTTP_NO_CONTENT).build();
    #     }
    #
