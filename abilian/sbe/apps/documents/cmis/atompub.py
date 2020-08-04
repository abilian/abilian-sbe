from typing import Callable

from flask import Blueprint, Response, make_response, render_template, request
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import NotFound, Unauthorized

from abilian.core.extensions import db
from abilian.sbe.apps.documents.repository import repository

from .parser import Entry
from .renderer import Feed, to_xml

#
# Constants
#


ROOT = "http://localhost:5000/cmis/atompub"

# MIME TYPES (cf. section 3.3 of the CMIS specs)
MIME_TYPE_ATOM_FEED = "application/atom+xml;type=feed"
MIME_TYPE_ATOM_ENTRY = "application/atom+xml;type=entry"
MIME_TYPE_ATOM_SERVICE = "application/atomsvc+xml"
MIME_TYPE_CMIS_ATOM = "application/cmisatom+xml"
MIME_TYPE_CMIS_QUERY = "application/cmisquery+xml"
MIME_TYPE_CMIS_ALLOWABLE_ACTIONS = "application/cmisallowableactions+xml"
MIME_TYPE_CMIS_TREE = "application/cmistree+xml"
MIME_TYPE_CMIS_ACL = "application/cmisacl+xml"

atompub = Blueprint("cmis", __name__, url_prefix="/cmis/atompub")
route = atompub.route


#
# Dummy for now
#
class Logger:
    def debug(self, msg):
        print(msg)


log = Logger()


def log_result(result):
    print(78 * "-")
    print("Response:")
    print(result)
    print(78 * "-")


def produces(*mimetypes) -> Callable:
    def decorator(f):
        return f

    return decorator


def consumes(mimetype):
    def decorator(f):
        return f

    return decorator


# NOT WORKING
#  def decorator(f):
#    def g(*args, **kw):
#      assert mimetype == request.content_type
#      return f(*args, **kw)
#    return g
#  return decorator


# NOT WORKING
def render(template, status=200, mimetype=None):
    def decorator(f):
        def g(*args, **kw):
            print(f, args, kw)
            result = f(*args, **kw)
            rendered = render_template(template, **result)
            headers = {"Content-Type": mimetype}
            response = make_response(rendered, status, headers)
            print(response)
            return response

        return g

    return decorator


BOOLEAN_OPTIONS = ["includeAllowableActions", "includeACL", "includePolicyIds"]


def get_options(args):
    d = {}
    for k in BOOLEAN_OPTIONS:
        v = args.get(k, "false").strip()
        if v == "true":
            v = True
        elif v in ("false", ""):
            v = False
        else:
            raise Exception(f"Unexpected parameter value for {k}: {v}")
        d[k] = v
    return d


def get_document(id):
    doc = repository.get_document_by_id(id)
    if not doc:
        raise NotFound
    return doc


def get_folder(id):
    obj = repository.get_folder_by_id(id)
    if not obj:
        raise NotFound
    return obj


def get_object(id):
    obj = repository.get_object_by_id(id)
    if not obj:
        raise NotFound
    return obj


#
# Authentication (basic)
#
# @atompub.before_request
def authenticate():
    if not request.authorization:
        raise Unauthorized()

    username = request.authorization.username
    password = request.authorization.password

    if (username, password) != ("admin", "admin"):
        raise Unauthorized()


# @atompub.errorhandler(401)
def custom_401(error):
    print("custom_401")
    return Response(
        "Authentication required",
        401,
        {"WWWAuthenticate": 'Basic realm="Login Required"'},
    )


@atompub.errorhandler(NoResultFound)
def not_found_error_handler(error):
    """Converts SQLAlchemy NoResultFound exception to an HTTP error."""
    return "This object does not exist", 404


#
# Service Document
#
# @render("cmis/service.xml", mimetype=MIME_TYPE_ATOM_SERVICE)
@route("/")
@produces(MIME_TYPE_ATOM_SERVICE)
def getRepositoryInfo():
    log.debug("repositoryInfo called")

    root_folder = repository.root_folder
    ctx = {"ROOT": ROOT, "root_folder": root_folder}

    result = render_template("cmis/service.xml", **ctx)
    response = Response(result, mimetype=MIME_TYPE_ATOM_SERVICE)
    # return {'root': ROOT}
    return response


#
# Service Collections
#
@route("/types")
def getTypeChildren():
    log.debug("getTypeChildren called")

    result = render_template("cmis/types.xml", ROOT=ROOT)
    return Response(result, mimetype=MIME_TYPE_ATOM_FEED)


@route("/types", methods=["POST"])
def createType():
    log.debug("createType called")
    raise NotImplementedError()


#
# Entries (Documents, Folders, Relationships, Policies & Items)
#
@route("/entry")
def getObject():
    id = request.args.get("id")
    path = request.args.get("path")

    log.debug(f"getObject called on id={id}, path={path}")
    log.debug("URL: " + request.url)

    options = get_options(request.args)
    log.debug(f"Options: {options}")

    if id:
        obj = repository.get_object_by_id(id)
    elif path:
        obj = repository.get_object_by_path(path)
    else:
        raise NotFound("You must supply either an id or a path.")
    if not obj:
        raise NotFound("Object not found")

    result = to_xml(obj, **options)
    return Response(result, mimetype=MIME_TYPE_ATOM_ENTRY)


@route("/entry", methods=["PUT"])
def updateProperties():
    id = request.args.get("id")
    if not id:
        path = request.args.get("path")
    else:
        path = ""
    log.debug(f"updateProperties called on id={id}, path={path}")
    log.debug("URL: " + request.url)

    obj = get_object(id)
    return Response(to_xml(obj), mimetype=MIME_TYPE_ATOM_ENTRY)


@route("/entry", methods=["DELETE"])
def deleteObject():
    id = request.args.get("id")
    if not id:
        path = request.args.get("path")
    else:
        path = ""
    log.debug(f"deleteObject called on id={id}, path={path}")
    log.debug("URL: " + request.url)

    obj = get_object(id)

    # TODO: remove
    parent = obj.parent
    if parent:
        child_count_0 = len(parent.children)

    db.session.delete(obj)
    db.session.commit()

    if parent:
        child_count_1 = len(parent.children)
        assert child_count_1 == child_count_0 - 1

    return ("", 204, {})


#
# Content Streams Ressource
#
@route("/content")
def getContentStream():
    id = request.args.get("id")
    log.debug("getContentStream called on " + id)

    document = get_document(id)
    return Response(document.content, mimetype=document.content_type)


# setContentStream + appendContentStream
@route("/content", methods=["PUT"])
def setContentStream():
    id = request.args.get("id")
    log.debug("setContentStream called on " + id)

    document = get_document(id)
    created = document.content is None

    document.content = request.data
    document.content_type = request.content_type
    db.session.commit()

    if created:
        return ("", 201, {})
    else:
        return ("", 204, {})


@route("/content", methods=["DELETE"])
def deleteContentStream():
    id = request.args.get("id")
    log.debug("deleteContentStream called on " + id)

    document = get_document(id)
    document.content = None
    db.session.commit()

    return ("", 204, {})


#
# Allowable Actions Resource
#
@route("/allowableactions")
def getAllowableActions():
    id = request.args.get("id")
    log.debug("getAllowableActions called on " + id)

    obj = get_object(id)
    args = {"ROOT": ROOT, "object": obj}
    result = render_template("cmis/allowableactions.xml", **args)
    return Response(result, mimetype=MIME_TYPE_CMIS_ALLOWABLE_ACTIONS)


#
# Type Entries
#
@route("/type")
def getTypeDefinition():
    type_id = request.args.get("id")
    log.debug("getTypeDefinition called on " + type_id)

    if type_id == "cmis:document":
        result = render_template("cmis/type-document.xml", ROOT=ROOT)
    elif type_id == "cmis:folder":
        result = render_template("cmis/type-folder.xml", ROOT=ROOT)
    elif type_id == "cmis:relationship":
        result = render_template("cmis/type-relationship.xml", ROOT=ROOT)
    elif type_id == "cmis:policy":
        result = render_template("cmis/type-policy.xml", ROOT=ROOT)
    else:
        raise NotImplementedError()

    return Response(result, mimetype=MIME_TYPE_ATOM_ENTRY)


@route("/type", methods=["POST"])
def updateType():
    raise NotImplementedError()


@route("/type", methods=["DELETE"])
def deleteType():
    raise NotImplementedError()
    # return ("", 204, {})


#
# Folder Children collection
#
@route("/children")
def getChildren():
    id = request.args.get("id")
    log.debug("getChildren called on " + id)
    log.debug("URL: " + request.url)

    folder = get_folder(id)

    args = {"ROOT": ROOT, "folder": folder, "to_xml": to_xml}
    result = render_template("cmis/children.xml", **args)
    log_result(result)
    return Response(result, mimetype=MIME_TYPE_ATOM_ENTRY)


@route("/children", methods=["POST"])
def createObject():
    id = request.args.get("id")
    log.debug("createObject called on " + id)
    log.debug("URL: " + request.url)

    print("Received:")
    print(request.data)

    folder = get_folder(id)

    entry = Entry(request.data)
    name = entry.name
    type = entry.type

    if type == "cmis:folder":
        new_object = folder.create_subfolder(name)
        db.session.commit()

    elif type == "cmis:document":
        new_object = folder.create_document(name)
        if entry.content:
            new_object.content = entry.content
            new_object.content_type = entry.content_type
        db.session.commit()

    else:
        raise Exception(f"Unknown object type: {type}")

    result = to_xml(new_object)
    log_result(result)
    return Response(result, status=201, mimetype=MIME_TYPE_ATOM_ENTRY)
    # TODO:
    # URI newloc = null;
    # try {
    #   newloc = new URI(getBase() + "/node/" + newdoc.getId());
    # } catch (URISyntaxException e) {
    # // Shouldn't happen.
    # e.printStackTrace();
    # }

    # String output = getTemplate("entry.ftl").arg("entry", newdoc)
    # .arg("parent", parent).arg("objectType", objectType).render();

    # // XXX: .type() is here because of a bug in resteasy
    # return Response.created(newloc).entity(output).type(MIME_TYPE_ATOM_ENTRY).build();


#
# Feeds
#
@route("/parents")
def getObjectParents():
    """Object Parents Feed (GET)."""
    id = request.args.get("id")
    log.debug("getObjectParents called on " + id)

    obj = get_object(id)
    if obj.parent:
        feed = Feed(obj, [obj.parent])
    else:
        feed = Feed(obj, [])
    result = feed.to_xml()
    return Response(result, mimetype=MIME_TYPE_ATOM_FEED)


# Changes Feed (GET)
@route("/changes")
def getContentChanges():
    log.debug("getContentChanges called")
    raise NotImplementedError()


# Folder Descendants Feed (GET, DELETE)
@route("/descendants")
def getDescendants():
    id = request.args.get("id")
    log.debug("getObjectParents called on " + id)
    raise NotImplementedError()


@route("/descendants", methods=["DELETE"])
@route("/foldertree", methods=["DELETE"])
def deleteTree():
    id = request.args.get("id")
    log.debug("deleteTree called on " + id)

    obj = get_object(id)
    db.session.delete(obj)
    db.session.commit()

    return ("", 204, {})


# Folder Tree Feed (GET, DELETE: see above)
@route("/foldertree")
def getFolderTree():
    id = request.args.get("id")
    log.debug("getFolderTree called on " + id)
    raise NotImplementedError()


# All Versions Feed (GET)
def getAllVersions():
    pass


# Type Descendants Feed (GET)
@route("/typedesc")
def getTypeDescendants():
    type_id = request.args.get("typeId")
    log.debug("getTypeDescendants called on " + type_id)

    feed = Feed({}, [])
    result = feed.to_xml()
    return Response(result, mimetype=MIME_TYPE_ATOM_FEED)


#
# Query Collection
#
@route("/query", methods=["POST"])
def query():
    q = request.form.get("q")
    log.debug("query called: " + q)
    raise NotImplementedError()
