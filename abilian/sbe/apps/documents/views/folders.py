# coding=utf-8
"""
"""
from __future__ import absolute_import

import fnmatch
import itertools
import logging
import os
import re
import tempfile
from cStringIO import StringIO
from datetime import datetime
from functools import partial
from urllib import quote
from zipfile import ZipFile, is_zipfile

import sqlalchemy as sa
import whoosh.query as wq
from flask import (Markup, current_app, flash, g, jsonify, make_response,
                   redirect, render_template, render_template_string, request,
                   send_file)
from sqlalchemy import func
from werkzeug.exceptions import InternalServerError
from xlwt import Workbook, easyxf

from abilian.core.extensions import db
from abilian.core.models.subjects import Group, User
from abilian.core.signals import activity
from abilian.i18n import _, _n
from abilian.sbe.apps.communities.views import default_view_kw
from abilian.services.security import READ, WRITE, Role, security
from abilian.web import csrf, http, url_for
from abilian.web.action import actions
from abilian.web.views import default_view

from ..models import Document, Folder, icon_for, icon_url
from ..repository import repository
from ..search import reindex_tree
from .util import (breadcrumbs_for, check_manage_access, check_read_access,
                   check_write_access, create_document, edit_object,
                   get_document, get_folder, get_new_filename,
                   get_selected_objects)
from .views import documents

route = documents.route


@route("/")
def index():
    folder = g.community.folder
    url = url_for(folder)
    return redirect(url)


@default_view(documents, Folder, id_attr='folder_id', kw_func=default_view_kw)
@route("/folder/<int:folder_id>")
def folder_view(folder_id):
    folder = get_folder(folder_id)
    bc = breadcrumbs_for(folder)
    actions.context['object'] = folder
    ctx = dict(folder=folder,
               children=folder.filtered_children,
               breadcrumbs=bc,
               csrf_token=csrf.field(),)
    return render_template("documents/folder.html", **ctx)


@route("/folder/<int:folder_id>/json")
def folder_json(folder_id):
    """Return parent folder + subfolders."""

    folder = get_folder(folder_id)
    folder_url = partial(url_for, '.folder_json')
    result = {}
    has_permission = security.has_permission
    result['current_folder_selectable'] = has_permission(
        g.user, WRITE, folder, inherit=True)
    folders = result['folders'] = []
    bc = result['breadcrumbs'] = []
    subfolders = sorted(
        (f
         for f in folder.subfolders
         if has_permission(g.user, READ, f, inherit=True)),
        key=lambda f: f.title)

    parent = folder

    # breadcrumbs
    for parent in reversed(list(folder._iter_to_root())):
        if parent.is_root_folder:
            continue

        data = {
            'id': parent.id,
            'url': folder_url(folder_id=parent.id,
                              community_id=parent.community.slug),
            'title': parent.title,
        }
        bc.append(data)

    if folder.parent is not None and not folder.parent.is_root_folder:
        # not at root folder: allow to go 1 level up
        data = bc[-2].copy()
        data['title'] = ".."
        folders.append(data)
    else:
        result['current_folder_selectable'] = False

    for folder in subfolders:
        data = {
            'id': folder.id,
            'url': folder_url(folder_id=folder.id,
                              community_id=folder.community.slug),
            'title': folder.title,
        }
        folders.append(data)

    return jsonify(result)


@route("/folder/<int:folder_id>/members")
def members(folder_id):
    folder = get_folder(folder_id)
    bc = breadcrumbs_for(folder)
    actions.context['object'] = folder
    members = folder.members()
    ctx = dict(folder=folder, members=members, breadcrumbs=bc)
    return render_template("community/members.html", **ctx)


@route("/folder/<int:folder_id>/permissions")
@http.nocache
def permissions(folder_id):
    folder = get_folder(folder_id)
    check_manage_access(folder)

    bc = breadcrumbs_for(folder)
    actions.context['object'] = folder
    local_roles_assignments = folder.get_local_roles_assignments()
    principals = set((p for p, r in local_roles_assignments))
    security._fill_role_cache_batch(principals)

    users_and_local_roles = [(user, role, repository.has_access(user, folder))
                             for user, role in local_roles_assignments
                             if isinstance(user, User)]
    groups_and_local_roles = [t
                              for t in local_roles_assignments
                              if isinstance(t[0], Group)]

    users_and_inherited_roles = groups_and_inherited_roles = ()

    if folder.inherit_security:
        inherited_roles_assignments = folder.get_inherited_roles_assignments()
        users_and_inherited_roles = [
            (user, role, False)
            for user, role in inherited_roles_assignments
            if isinstance(user, User)
        ]
        groups_and_inherited_roles = [t
                                      for t in inherited_roles_assignments
                                      if isinstance(t[0], Group)]

    query = Group.query
    query = query.order_by(func.lower(Group.name))
    all_groups = query.all()

    class EntryPresenter(object):
        _USER_FMT = (u'<a href="{{ url_for("social.user", user_id=user.id) }}">'
                     '{{ user.name }}</a>')
        _GROUP_FMT = (
            u'<a href="{{ url_for("social.group_home", group_id=group.id)'
            ' }}">{{ group.name }}</a>')

        def __init__(self, e):
            render = render_template_string
            self.entry = e
            self.date = e.happened_at.strftime('%Y-%m-%d %H:%M')
            self.manager = render(
                u'<img src="{{ user_photo_url(e.manager, size=16) }}" alt="" />'
                '<a href="{{ url_for("social.user", user_id=e.manager_id) }}">'
                '{{ e.manager.name }}</a>',
                e=e)

            if e.op == e.SET_INHERIT:
                msg = _(u'On {date}, {manager} has activated inheritance')
            elif e.op == e.UNSET_INHERIT:
                msg = _(u'On {date}, {manager} has deactivated inheritance')
            elif e.op == e.GRANT:
                msg = _(u'On {date}, {manager} has given role "{role}" to {principal}')
            elif e.op == e.REVOKE:
                msg = _(u'On {date}, {manager} has revoked role "{role}" from '
                        '{principal}')
            else:
                raise Exception("Unknown audit entry type %s" % e.op)

            principal = u''
            if self.entry.user:
                principal = render(self._USER_FMT, user=self.entry.user)
            elif self.entry.group:
                principal = render(self._GROUP_FMT, group=self.entry.group)

            self.msg = Markup(msg.format(date=self.date,
                                         manager=self.manager,
                                         role=self.entry.role,
                                         principal=principal))

    audit_entries = [EntryPresenter(e) for e in security.entries_for(folder)]
    csrf_token = csrf.field()

    ctx = dict(folder=folder,
               users_and_local_roles=users_and_local_roles,
               users_and_inherited_roles=users_and_inherited_roles,
               groups_and_local_roles=groups_and_local_roles,
               groups_and_inherited_roles=groups_and_inherited_roles,
               audit_entries=audit_entries,
               csrf_token=csrf_token,
               all_groups=all_groups,
               breadcrumbs=bc)

    return render_template("documents/permissions.html", **ctx)


@route("/folder/<int:folder_id>/permissions", methods=['POST'])
@csrf.protect
def permissions_update(folder_id):
    folder = repository.get_folder_by_id(folder_id)
    check_manage_access(folder)
    has_permission = security.has_permission
    action = request.form.get("action")

    if action in ("activate_inheritance", "deactivate_inheritance"):
        inherit_security = (action == "activate_inheritance")

        if not (inherit_security or
                has_permission(g.user, 'manage',
                               folder, inherit=False)):
            # don't let user shoot himself in the foot
            flash(_(u'You must have the "manager" local role on this folder in '
                    'order to deactivate inheritance.'), u'error')
            return redirect(url_for(".permissions",
                                    folder_id=folder_id,
                                    community_id=folder.community.slug))

        security.set_inherit_security(folder, inherit_security)
        db.session.add(folder)
        reindex_tree(folder)
        db.session.commit()
        return redirect(url_for(".permissions",
                                folder_id=folder_id,
                                community_id=folder.community.slug))

    elif action == "add-user-role":
        role = request.form.get("role").lower()
        user_id = int(request.form.get("user"))
        user = User.query.get(user_id)

        security.grant_role(user, role, folder)
        reindex_tree(folder)
        db.session.commit()
        return redirect(url_for(".permissions",
                                folder_id=folder_id,
                                community_id=folder.community.slug))

    elif action == "add-group-role":
        role = request.form.get("role").lower()
        group_id = int(request.form.get("group"))
        group = Group.query.get(group_id)

        security.grant_role(group, role, folder)
        reindex_tree(folder)
        db.session.commit()
        return redirect(url_for(".permissions",
                                folder_id=folder_id,
                                community_id=folder.community.slug))

    else:
        action, args = request.form.items()[0]
        role, object_id = args.split(":")
        role = role.lower()
        object_id = int(object_id)

        if action == 'delete-user-role':
            user = User.query.get(object_id)
            # remove role in a subtransaction, to prevent manager shoot himself in the
            # foot
            transaction = db.session.begin_nested()
            security.ungrant_role(user, role, folder)

            if (user == g.user and role == 'manager' and not has_permission(
                    g.user, 'manage', folder,
                    inherit=True)):

                transaction.rollback()
                flash(_(u'Cannot remove "manager" local role for yourself: you '
                        'don\'t have "manager" role (either by security inheritance '
                        'or by group membership)'),
                      'error')
            else:
                reindex_tree(folder)
                transaction.commit()
                flash(_(u"Role {role} for user {user} removed on folder {folder}"
                ).format(role=role, user=user.name, folder=folder.name),
                      "success")
        elif action == 'delete-group-role':
            group = Group.query.get(object_id)
            # remove role in a subtransaction, to prevent manager shoot himself in the
            # foot
            transaction = db.session.begin_nested()
            security.ungrant_role(group, role, folder)

            if (role == 'manager' and not has_permission(
                    g.user, 'manage', folder,
                    inherit=True)):
                transaction.rollback()
                flash(_(u'Cannot remove "manager" local role for group "{group}": you'
                        ' don\'t have "manager" role by security inheritance or by '
                        'local role').format(group=group.name),
                      'error')
            else:
                flash(_(u"Role {role} for group {group} removed on folder {folder}"
                ).format(role=role, group=group.name, folder=folder.name),
                      "success")
                reindex_tree(folder)
                transaction.commit()

        db.session.commit()
        return redirect(url_for(".permissions",
                                folder_id=folder_id,
                                community_id=folder.community.slug))


@route("/folder/<int:folder_id>/permissions_export")
@http.nocache
def permissions_export(folder_id):
    folder = repository.get_folder_by_id(folder_id)
    check_manage_access(folder)

    wb = Workbook()
    ws = wb.add_sheet("Sheet 1")

    cols = [
        (u'Accès', 20),
        (u'Identifiant', 40),
        (u'Prénom', 14),
        (u'Nom', 20),
        (u'Rôle', None),
        (u'Local', None),
        (u'Héritage', None),
        (u'Communauté', 60),
    ]

    # styling
    # from xlwt doc: width unit is 1/256 of '0' from first font in excel file
    for c, width in enumerate((c[1] for c in cols)):
        if width is not None:
            ws.col(c).width = 256 * width

    ws.row(0).height = 256 + 128

    ws.panes_frozen = True
    ws.remove_splits = True
    ws.horz_split_pos = 1

    header_style = easyxf('font: bold true;'
                          'alignment: horizontal center, vertical center;')
    for c, val in enumerate((c[0] for c in cols)):
        ws.write(0, c, val, header_style)

    # data
    permissions = iter_permissions(folder, g.user)
    row_offset = 0
    current_community = None
    for r, row in enumerate(permissions, 1):
        if current_community is None:
            current_community = row[-1]

        if current_community != row[-1]:
            current_community = row[-1]
            row_offset += 1

        # data grouping enter (refered as 'outline' in xlwt documention)
        ws.row(r + row_offset).level = 1

        for c, value in enumerate(row):
            if isinstance(value, Role):
                value = unicode(value)
            ws.write(r + row_offset, c, value)

        # data grouping exit
        ws.row(r + row_offset).level = 1

    debug = request.args.get('debug_sql')
    if debug:
        # useful only in DEBUG mode, to get the debug toolbar in browser
        return '<html><body>Exported</body></html>'

    fd = StringIO()
    wb.save(fd)

    response = make_response(fd.getvalue())
    response.headers['content-type'] = 'application/ms-excel'
    folder_name = folder.title.replace(u' ', u'_')
    file_date = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    filename = u'permissions-{}-{}.xls'.format(folder_name, file_date)
    content_disposition = u'attachment;filename="{}"'.format(filename)
    response.headers['content-disposition'] = content_disposition
    return response


def iter_permissions(folder, user):
    """
    Iterator returning permissions settings on folder and its subfolders tree.
    """
    if not security.has_permission(user, "manage", folder, inherit=True):
        raise StopIteration

    community = folder.path
    local_roles = frozenset(folder.get_local_roles_assignments())
    inherited_roles = frozenset((folder.get_inherited_roles_assignments() if
                                 folder.inherit_security else []))

    result = {}
    for principal, role in (local_roles | inherited_roles):
        data = result.setdefault((principal, role), {})
        data['local'] = (principal, role) in local_roles
        data['inherit'] = (principal, role) in inherited_roles

    def _sort_key(item):
        """ Sorts by name, groups first. """
        principal = item[0][0]
        is_user = isinstance(principal, User)
        item_key = [is_user]
        if is_user:
            last_name = principal.last_name if principal.last_name else u''
            first_name = principal.first_name if principal.first_name else u''
            item_key.append(last_name.lower())
            item_key.append(first_name.lower())
        else:
            item_key.append(principal.name)
        return item_key

    for (p, role), data in sorted(result.items(), key=_sort_key):
        is_user = isinstance(p, User)
        has_access = False if is_user else '*'
        identifier = p.email if is_user else u'* Group *'
        first_name = p.first_name if is_user else u'-'
        last_name = p.last_name if is_user else p.name
        local = data['local']
        inherit = data['inherit']

        yield (has_access, identifier, first_name, last_name, role, local,
               inherit, community)

    subfolders = (f
                  for f in folder.subfolders
                  if security.has_permission(user, "manage", folder))

    for subfolder in subfolders:
        for permission in iter_permissions(subfolder, user):
            yield permission


#
# Actions on folders
#
@route("/folder/<int:folder_id>", methods=['POST'])
@csrf.protect
def folder_post(folder_id):
    """
    A POST on a folder can result on several different actions (depending on the
    `action` parameter).
    """
    folder = get_folder(folder_id)
    action = request.form.get("action")

    if action == 'edit':
        return folder_edit(folder)

    elif action == 'upload':
        return upload_new(folder)

    elif action == 'download':
        return download_multiple(folder)

    elif action == 'delete':
        return delete_multiple(folder)

    elif action == 'new':
        return create_subfolder(folder)

    elif action == 'move':
        return move_multiple(folder)

    elif action == 'change-owner':
        return change_owner(folder)

    else:
        # Probably an error or a hack attempt.
        # Logger will inform sentry if enabled
        logger = logging.getLogger(__name__)
        logger.error(u"Unknown folder action.", extra={'stack': True})
        flash(_(u"Unknown action."), "error")
        return redirect(url_for(folder))


def folder_edit(folder):
    check_write_access(folder)

    changed = edit_object(folder)

    if changed:
        db.session.commit()
        flash(_(u"Folder properties successfully edited."), "success")
    else:
        flash(_(u"You didn't change any property."), "success")
    return redirect(url_for(folder))


ARCHIVE_IGNORE_FILES = {u'__MACOSX/*', u'.DS_Store',}
# translates patterns to match with any parent directory ((*/)?pattern should
# match)
ARCHIVE_IGNORE_FILES = {re.compile(u'(?:.*\\/)?' + fnmatch.translate(pattern))
                        for pattern in ARCHIVE_IGNORE_FILES}

# skip directory names. Directory will be created only if they contains files
ARCHIVE_IGNORE_FILES.add(re.compile(fnmatch.translate(u'*/')))


def explore_archive(fd, filename=None, uncompress=False):
    """
    Given an uploaded file descriptor, return it or a list of archive
    content.

    Yield tuple(filepath, file-like object), where filepath is a list
    whose components are directories and last one is filename.
    """
    if filename is None:
        filename = fd.filename

    if not isinstance(filename, unicode):
        filename = unicode(fd.filename, errors='ignore')

    if not uncompress:
        yield [], fd
        raise StopIteration

    if is_zipfile(fd):
        with ZipFile(fd, 'r') as archive:
            for zipinfo in archive.infolist():
                filename = zipinfo.filename
                if isinstance(filename, bytes):
                    # not unicode: try to convert from utf-8 (OSX case: unicode flag not
                    # set), then legacy cp437
                    # http://stackoverflow.com/questions/13261347/correctly-decoding-zip-entry-file-names-cp437-utf-8-or
                    try:
                        filename = filename.decode('utf-8')
                    except UnicodeDecodeError:
                        filename = filename.decode('cp437')

                if any(pattern.match(filename) is not None
                       for pattern in ARCHIVE_IGNORE_FILES):
                    continue

                filepath = filename.split(u'/')
                filename = filepath.pop()
                zip_fd = archive.open(zipinfo, 'r')
                setattr(zip_fd, 'filename', filename)
                setattr(zip_fd, 'content_type', None)
                yield filepath, zip_fd
    else:
        yield [], fd


def upload_new(folder):
    check_write_access(folder)
    session = current_app.db.session()
    base_folder = folder
    uncompress_files = 'uncompress_files' in request.form
    fds = request.files.getlist('file')
    created_count = 0
    path_cache = {}  # mapping folder path in zip: folder instance

    for upload_fd in fds:
        for filepath, fd in explore_archive(upload_fd,
                                            uncompress=uncompress_files):
            folder = base_folder
            parts = []
            # traverse to final directory, create intermediate if necessary. Folders
            # may be renamed if a file already exists, path_cache is used to keep
            # track of this
            for subfolder_name in filepath:
                parts.append(subfolder_name)
                path = u'/'.join(parts)
                if path in path_cache:
                    folder = path_cache[path]
                    continue

                subfolders = {f.title: f for f in folder.subfolders}
                if subfolder_name in subfolders:
                    folder = subfolders[subfolder_name]
                    path_cache[path] = folder
                    continue

                subfolder_name = get_new_filename(folder, subfolder_name)
                folder = folder.create_subfolder(subfolder_name)
                session.flush()
                path_cache[path] = folder

            create_document(folder, fd)
            created_count += 1

    flash(
        _n(u"One new document successfully uploaded",
           u"%(num)d new document successfully uploaded",
           num=created_count),
        "success")

    session.commit()
    return redirect(url_for(folder))


def download_multiple(folder):
    folders, docs = get_selected_objects(folder)

    def rel_path(path, content):
        return u'{}/{}'.format(path, content.title)

    def zip_folder(zipfile, folder, path=u''):
        for doc in folder.documents:
            doc_path = rel_path(path, doc)
            zipfile.writestr(doc_path, doc.content)

        for subfolder in folder.filtered_subfolders:
            zip_folder(zipfile, subfolder, rel_path(path, subfolder))
        return zipfile

    # if using upstream send file: just create a temps file.
    # if app is streaming itself: use NamedTemporaryFile so that file is removed
    # on close()
    temp_factory = (tempfile.mktemp if current_app.use_x_sendfile else
                    tempfile.NamedTemporaryFile)
    zip_fn = temp_factory(prefix='tmp-' + current_app.name + '-', suffix='.zip')
    with ZipFile(zip_fn, "w") as zipfile:
        for doc in docs:
            zipfile.writestr(doc.title, doc.content)
        for subfolder in folders:
            zip_folder(zipfile, subfolder, subfolder.title)

    if not isinstance(zip_fn, str):
        zip_fn.seek(0, os.SEEK_END)
        size = zip_fn.tell()
        zip_fn.seek(0)
    else:
        size = os.path.getsize(zip_fn)

    resp = send_file(
        zip_fn,
        mimetype="application/zip",
        as_attachment=True,
        attachment_filename=quote(folder.title.encode("utf8") + ".zip"))
    resp.headers.add('Content-Length', str(size))
    return resp


def delete_multiple(folder):
    check_write_access(folder)

    folders, docs = get_selected_objects(folder)

    for obj in docs + folders:
        app = current_app._get_current_object()
        community = g.community._model
        activity.send(app,
                      actor=g.user,
                      verb="delete",
                      object=obj,
                      target=community)
        repository.delete_object(obj)

    if docs + folders:
        db.session.commit()
        if docs and folders:
            msg = _(u"%(file_num)d files and %(folder_num)d folders sucessfully "
                    "deleted.", file_num=len(docs), folder_num=len(folders))
        elif docs and not folders:
            msg = _n("1 file sucessfully deleted.",
                     "%(num)d files sucessfully deleted.",
                     num=len(docs))
        else:
            msg = _n("1 folder sucessfully deleted.",
                     "%(num)d folders sucessfully deleted.",
                     num=len(folders))

        flash(msg, "success")
    else:
        flash(_(u"No object deleted"), "error")

    return redirect(url_for(folder))


def move_multiple(folder):
    folders, docs = get_selected_objects(folder)
    count_f = len(folders)
    count_d = len(docs)
    current_folder_url = url_for(folder)

    if not (count_f + count_d):
        flash(_(u'Move elements: no elements selected.'), 'info')
        return redirect(current_folder_url)

    try:
        target_folder_id = int(request.form.get('target-folder'))
    except ValueError:
        flash(_(u'Move elements: no destination folder selected. Aborted.'),
              'error')
        return redirect(current_folder_url)

    target_folder = repository.get_folder_by_id(target_folder_id)

    if folder == target_folder:
        flash(_(u'Move elements: source and destination folder are identical,'
                ' nothing done.'), 'error')
        return redirect(current_folder_url)

    if not security.has_permission(g.user, 'write', folder, inherit=True):
        # this should not happen: this is just defensive programming
        flash(_(u'You are not allowed to move elements from this folder'), 'error')
        return redirect(current_folder_url)

    if not security.has_permission(
            g.user, 'write', target_folder,
            inherit=True):
        flash(_(u'You are not allowed to write in folder "{folder}"'
        ).format(folder=target_folder.title),
              'error')
        return redirect(current_folder_url)

    for item in itertools.chain(folders, docs):
        # FIXME: maybe too brutal
        check_write_access(item)

    # verify we are not trying to move a folder inside itself or one of its
    # descendants
    f = target_folder
    while f:
        if f in folders:
            flash(_(u'Move elements: destination folder is included in moved '
                    'elements. Moved nothing.'), 'error')
            return redirect(url_for(folder))
        f = f.parent

    exist_in_dest = []
    for item in itertools.chain(folders, docs):
        try:
            with db.session.begin_nested():
                item.parent = target_folder
        except sa.exc.IntegrityError:
            exist_in_dest.append(item)

    if exist_in_dest:
        # items existing in destination: cancel operation
        db.session.rollback()
        msg = _(u'Move elements: canceled, some elements exists in destination '
                u'folder: {elements}')
        elements = u', '.join(u'"{}"'.format(i.title) for i in exist_in_dest)
        flash(msg.format(elements=elements), 'error')
        return redirect(current_folder_url)

    db.session.commit()

    msg_f = (_n(u'1 folder', u'{count} folders', count_f)
             if count_f
             else _(u'0 folder')).format(count=count_f)

    msg_d = (_n(u'1 document', u'{count} documents', count_d)
             if count_d
             else _(u'0 document')).format(count=count_d)

    msg = _(u'{folders} and {documents} moved to {target}').format(
        folders=msg_f, documents=msg_d, target=target_folder.title)
    flash(msg, 'success')

    return redirect(url_for(folder))


def create_subfolder(folder):
    check_write_access(folder)

    title = request.form.get("title", u"")
    description = request.form.get("description", u"")
    subfolder = folder.create_subfolder(title)
    subfolder.description = description

    db.session.commit()
    return redirect(url_for(folder))


def change_owner(folder):
    check_manage_access(folder)
    items = itertools.chain(*get_selected_objects(folder))

    user_id = request.form.get('new_owner', type=int)
    user = User.query.get(user_id)

    for item in items:
        item.owner = user

    db.session.commit()
    return redirect(url_for(folder))


@route("/folder/check_valid_name")
@http.nocache
def check_valid_name():
    """Check if name is valid for content creation in this folder."""

    object_id = int(request.args.get('object_id'))
    action = request.args.get('action')
    title = request.args.get('title')

    get_object = get_document if action == 'document-edit' else get_folder
    obj = get_object(object_id)
    check_read_access(obj)

    if action == u'new':
        parent = obj
        help_text = _(u'An element named "{name}" is already present in folder')
    elif action in (u'folder-edit', u'document-edit'):
        parent = obj.parent
        help_text = _(u'Cannot rename: "{name}" is already present in parent '
                      'folder')
    else:
        raise InternalServerError()

    existing = set((e.title for e in parent.children))

    if action in (u'folder-edit', u'document-edit'):
        try:
            existing.remove(obj.title)
        except KeyError:
            pass

    result = {}
    valid = result['valid'] = title not in existing
    if not valid:
        result['help_text'] = help_text.format(name=title)

    return jsonify(result)


@route("/folder/<int:folder_id>/descendants")
def descendants_view(folder_id):
    folder = get_folder(folder_id)
    bc = breadcrumbs_for(folder)
    actions.context['object'] = folder

    root_path_ids = folder._indexable_parent_ids + u'/{}'.format(folder.id)
    svc = current_app.services['indexing']
    filters = wq.And([wq.Term('community_id', folder.community.id), wq.Term(
        'parent_ids', root_path_ids), wq.Or([wq.Term(
            'object_type', Folder.entity_type), wq.Term(
                'object_type', Document.entity_type)])])

    results = svc.search(u'', filter=filters, limit=None)
    by_path = {}
    owner_ids = set()
    for hit in results:
        by_path.setdefault(hit['parent_ids'], []).append(hit)
        owner_type, owner_id = hit['owner'].split(u':')
        if owner_type == u'user':
            try:
                owner_id = int(owner_id)
                owner_ids.add(owner_id)
            except ValueError:
                pass

    for children in by_path.values():
        children.sort(
            key=
            lambda hit: (hit['object_type'] != Folder.entity_type, hit['name'].lower()))

    descendants = []

    def visit(path_id, level=0):
        children = by_path.get(path_id, ())

        for child in children:
            is_folder = child['object_type'] == Folder.entity_type
            type_letter = u'F' if is_folder else u'D'
            descendants.append((level, type_letter, child))

            if is_folder:
                path_id = child['parent_ids'] + u'/{}'.format(child['id'])
                visit(path_id, level + 1)

    visit(root_path_ids, 0)

    owners = dict()
    owners_q = User.query \
        .filter(User.id.in_(owner_ids)) \
        .add_column(sa.sql.func.concat('user:', User.id).label('key'))
    for user, key in owners_q:
        owners[key] = user

    ctx = dict(folder=folder,
               descendants=descendants,
               owners=owners,
               breadcrumbs=bc,
               get_icon=get_icon_for_hit,
               csrf_token=csrf.field(),)
    return render_template("documents/descendants.html", **ctx)


def get_icon_for_hit(hit):
    if hit['object_type'] == Folder.entity_type:
        return icon_url('folder.png')

    content_type = hit['content_type']
    icon = icon_for(content_type)
    return icon
