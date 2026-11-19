# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import chain
from typing import TYPE_CHECKING

import pytz
import sqlalchemy as sa
import sqlalchemy.orm
from flask import (
    Response,
    get_template_attribute,
    render_template,
    render_template_string,
    request,
)
from markupsafe import Markup
from werkzeug.exceptions import BadRequest
from werkzeug.routing import BuildError

from abilian.core.entities import Entity, all_entity_classes
from abilian.core.extensions import db
from abilian.core.models.subjects import User
from abilian.core.util import local_dt
from abilian.i18n import _, _l
from abilian.services.audit import CREATION, DELETION, UPDATE, AuditEntry
from abilian.services.security import SecurityAudit
from abilian.web.admin import AdminPanel
from abilian.web.util import url_for
from abilian.web.views.base import JSONView

if TYPE_CHECKING:
    from collections.abc import Callable

    from werkzeug.datastructures import MultiDict


class JSONUserSearch(JSONView):
    """Search users by fullname."""

    def data(self, *args, **kwargs) -> dict:
        q = kwargs.get("q", "").replace("%", " ").strip().lower()
        if len(q) < 2:
            raise BadRequest

        query = User.query
        lower = sa.sql.func.lower
        filters = []
        for part in q.split(" "):
            filters.append(
                sa.sql.or_(
                    lower(User.first_name).like(f"{part}%"),
                    lower(User.last_name).like(f"{part}%"),
                )
            )

        filters = sa.sql.and_(*filters) if len(filters) > 1 else filters[0]

        if "@" in q:
            # FIXME: where does this 'part' variable come from ?
            filters = sa.sql.or_(lower(User.email).like(f"%{part}%"), filters)

        query = query.filter(filters).order_by(User.last_name, User.first_name)

        values = query.values(User.id, User.first_name, User.last_name, User.email)
        results = [
            {"id": obj.id, "text": f"{obj.first_name} {obj.last_name} ({obj.email})"}
            for obj in values
        ]

        return {"results": results}


class AuditPanel(AdminPanel):
    """Global audit log.

    Can receive one out of two possible GET parameter, datetime type:

    * before: events that happened immediately before 't' (less recent than 't')
    * after: events that happened immediately after 't' (more recent than 't')
    """

    id = "audit"
    label = _l("Log")
    icon = "list-alt"

    def install_additional_rules(self, add_url_rule: Callable) -> None:
        add_url_rule("/search_users", view_func=JSONUserSearch.as_view("search_users"))
        add_url_rule("/export", "export", view_func=export_log)

    def get(self) -> str:
        LIMIT = 30

        log = log_filter(request.args)
        base_audit_q = log.audit_q
        base_security_q = log.security_q
        filter_user = log.user
        filter_types = log.types
        all_classes = log.all_classes

        before = request.args.get("before")
        after = request.args.get("after")

        def after_query(q, model, date):
            return q.filter(model.happened_at > date).order_by(model.happened_at.asc())

        def before_query(q, model, date):
            return q.filter(model.happened_at < date).order_by(model.happened_at.desc())

        if after:
            after = page_moment(after)
            audit_q = after_query(base_audit_q, AuditEntry, after)
            security_q = after_query(base_security_q, SecurityAudit, after)
        else:
            before = page_moment(before) if before else datetime.utcnow()
            audit_q = before_query(base_audit_q, AuditEntry, before)
            security_q = before_query(base_security_q, SecurityAudit, before)

        audit_entries = (
            audit_q.options(sa.orm.joinedload(AuditEntry.entity)).limit(LIMIT).all()
        )
        security_entries = (
            security_q.options(sa.orm.joinedload(SecurityAudit.object))
            .limit(LIMIT)
            .all()
        )
        # audit_entries = []
        all_entries = sorted(
            chain(
                #
                (AuditEntryPresenter(e) for e in audit_entries),
                #
                (SecurityEntryPresenter(e) for e in security_entries),
            )
        )

        if after:
            all_entries = all_entries[:LIMIT]
        else:
            all_entries = all_entries[-LIMIT:]

        all_entries.reverse()  # event are presented from most to least recent

        # group entries by day
        entries = []
        day_entries: list[BaseEntryPresenter] = []
        current_day = None

        for e in all_entries:
            e_date = e.date

            if e_date.date() != current_day:
                current_day = e_date.date()
                day_entries = []
                entries.append((e_date.date(), day_entries))
            day_entries.append(e)

        top_date = ""
        lowest_date = ""

        if entries:
            # top_date and lowest_date are converted to naive datetimes (from UTC):
            # their isoformat then carries no zone, as the entries are stored.
            top_date = entries[0][1][0].date.astimezone(pytz.utc).replace(tzinfo=None)
            lowest_date = (
                entries[-1][1][-1].date.astimezone(pytz.utc).replace(tzinfo=None)
            )

            after_queries = (
                after_query(base_audit_q, AuditEntry, top_date),
                after_query(base_security_q, SecurityAudit, top_date),
            )

            before_queries = (
                before_query(base_audit_q, AuditEntry, lowest_date),
                before_query(base_security_q, SecurityAudit, lowest_date).limit(1),
            )

            if not any(q.limit(1).first() is not None for q in after_queries):
                top_date = ""
            else:
                top_date = top_date.isoformat()

            if not any(q.first() is not None for q in before_queries):
                lowest_date = ""
            else:
                lowest_date = lowest_date.isoformat()

        current_date = None
        if entries:
            current_date = entries[0][0].isoformat()

        # build prev/next urls
        url_params = {}
        if filter_user:
            url_params["user"] = filter_user.id
        if filter_types:
            url_params["types"] = next(iter(filter_types))
        if log.period:
            url_params["period"] = log.period

        ctx = {
            "entries": entries,
            "periods": PERIODS,
            "period": log.period,
            "total": base_audit_q.count() + base_security_q.count(),
            "filter_user": filter_user,
            "all_classes": [(c.__name__, c.entity_type) for c in all_classes],
            "filter_types": filter_types,
            "url_params": url_params,
            "current_date": current_date,
            "top_date": top_date,
            "lowest_date": lowest_date,
        }
        return render_template("admin/audit.html", **ctx)


#: The log's periods: the name in the address, what the page calls it.
PERIODS = {
    "week": _l("The last 7 days"),
    "month": _l("The last 30 days"),
    "year": _l("This year"),
}


@dataclass(frozen=True)
class LogFilter:
    """The changes and the roles given or taken that the log shows, filtered."""

    audit_q: sa.orm.Query
    security_q: sa.orm.Query
    user: User | None
    types: set[str]
    period: str | None
    all_classes: list[type[Entity]]


def log_filter(args: MultiDict[str, str]) -> LogFilter:
    """The log filtered as `args` say: by `user`, by `types` of object, by `period`."""
    audit_q = AuditEntry.query
    security_q = SecurityAudit.query

    user = None
    user_id = args.get("user")
    if user_id:
        if not user_id.isdigit():
            raise BadRequest
        user = User.query.get(int(user_id))
        audit_q = audit_q.filter(AuditEntry.user == user)
        security_q = security_q.filter(SecurityAudit.manager == user)

    all_classes = sorted(all_entity_classes(), key=lambda c: c.__name__)
    types = set(args.getlist("types")) & {c.entity_type for c in all_classes}
    if types:
        audit_q = audit_q.filter(AuditEntry.entity_type.in_(types))
        security_q = (
            security_q.join(SecurityAudit.object)
            .filter(
                sa.sql.or_(SecurityAudit.object == None, Entity._entity_type.in_(types))
            )
            .reset_joinpoint()
        )

    period = args.get("period") or None
    start = period_start(period, datetime.utcnow())
    if start is not None:
        audit_q = audit_q.filter(AuditEntry.happened_at >= start)
        security_q = security_q.filter(SecurityAudit.happened_at >= start)

    return LogFilter(audit_q, security_q, user, types, period, all_classes)


def page_moment(value: str) -> datetime:
    """A page's edge in the address: an ISO date, with or without its fraction of a
    second (an entry at a whole second has none)."""
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise BadRequest from e


def period_start(period: str | None, now: datetime) -> datetime | None:
    """Where `period` starts, counted back from `now`; None for the whole log."""
    match period:
        case None:
            return None
        case "week":
            return now - timedelta(days=7)
        case "month":
            return now - timedelta(days=30)
        case "year":
            return datetime(now.year, 1, 1)
    raise BadRequest


#: The most lines an export holds: the latest.
EXPORT_LIMIT = 10_000

#: What a line of the export says was done, by kind of change.
EXPORTED_ACTIONS = {
    "create": _l("created"),
    "update": _l("changed"),
    "delete": _l("deleted"),
    SecurityAudit.GRANT: _l("role given"),
    SecurityAudit.REVOKE: _l("role taken back"),
    SecurityAudit.SET_INHERIT: _l("inherited rights turned on"),
    SecurityAudit.UNSET_INHERIT: _l("inherited rights turned off"),
}


def export_log() -> Response:
    """The log as filtered, as a spreadsheet (CSV), the latest first."""
    log = log_filter(request.args)
    audit = log.audit_q.order_by(AuditEntry.happened_at.desc()).limit(EXPORT_LIMIT)
    security = log.security_q.order_by(SecurityAudit.happened_at.desc()).limit(
        EXPORT_LIMIT
    )
    rows = sorted(
        chain(map(audit_row, audit), map(security_row, security)), reverse=True
    )
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            _("Date"),
            _("Person"),
            _("E-mail"),
            _("Action"),
            _("Kind"),
            _("Object"),
            _("Detail"),
        ]
    )
    writer.writerows(
        [spreadsheet_cell(cell) for cell in row[1:]] for row in rows[:EXPORT_LIMIT]
    )
    # The mark tells spreadsheets the file is in UTF-8.
    return Response(
        "\ufeff" + out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=log.csv"},
    )


#: A line of the export, behind the moment that orders it.
Row = tuple[datetime, str, str, str, str, str, str, str]


def audit_row(entry: AuditEntry) -> Row:
    """A change to an object, as a line of the export."""
    verb = AuditEntryPresenter(entry).verb
    detail = ", ".join(entry.changes.shown_columns()) if verb == "update" else ""
    return (
        *_when_and_who(entry.happened_at, entry.user),
        str(EXPORTED_ACTIONS[verb]),
        entry.entity_type.rsplit(".", 1)[-1],
        entry.entity_name or "",
        detail,
    )


def security_row(entry: SecurityAudit) -> Row:
    """A role given or taken, or inherited rights turned on or off, as a line."""
    principal = entry.user or entry.group
    detail = f"{entry.role} → {principal.name}" if principal and entry.role else ""
    return (
        *_when_and_who(entry.happened_at, entry.manager),
        str(EXPORTED_ACTIONS[entry.op]),
        (entry.object_type or "").rsplit(".", 1)[-1],
        entry.object_name or "",
        detail,
    )


def _when_and_who(
    happened_at: datetime | None, user: User | None
) -> tuple[datetime, str, str, str]:
    """The moment, to order lines by; when, as the site's time shows it; then who,
    by name and address."""
    # Set on insert by the columns' default; the models type them as nullable.
    assert happened_at is not None
    when = local_dt(happened_at).strftime("%Y-%m-%d %H:%M")
    if user is None:
        return happened_at, when, str(_("System")), ""
    return happened_at, when, user.name, user.email


def spreadsheet_cell(value: str) -> str:
    """`value`, which a spreadsheet will not run as a formula: one that starts as a
    formula does is read as text."""
    return f"'{value}" if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


#
#  Presenters for audit entries listing
#
class BaseEntryPresenter:
    _USER_FMT = (
        '<a href="{{ url_for("social.user", user_id=user.id) }}"> {{ user.name }}</a>'
    )
    #: A group has no page of its own any more: its name alone.
    _GROUP_FMT = "{{ group.name }}"

    def __init__(self, user, date) -> None:
        self.user = user
        self.date = local_dt(date)

    def __lt__(self, other):
        return self.date < other.date

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.user!r}, {self.date!r} @ {id(self)})"

    @staticmethod
    def model(model_name):
        return db.Model.registry._class_registry.get(model_name)

    def render_user(self, user: User | None) -> str:
        """Render the actor of an entry, which may not be one.

        `AuditEntry.user_id` is nullable: anything done outside a request --
        a migration, the CLI, `create_root_user` -- is recorded with no actor.
        Only one of the two presenters below used to allow for that, and the
        other took the whole admin audit panel down with an AttributeError the
        first time it met such an entry.
        """
        if user is None:
            return Markup("<em>{}</em>").format(_("System"))
        return render_template_string(self._USER_FMT, user=user)

    def render(self) -> str:
        raise NotImplementedError


class AuditEntryPresenter(BaseEntryPresenter):
    def __init__(self, entry: AuditEntry) -> None:
        assert isinstance(entry, AuditEntry)
        super().__init__(entry.user, entry.happened_at)
        self.entry = entry
        self.entity_deleted = entry.entity is None

    @property
    def verb(self) -> str:
        """What was done: "create", "update" (a related object's change is one
        too) or "delete"."""
        e = self.entry
        if e.type == CREATION:
            return "create"
        if e.related or e.op == UPDATE:
            return "update"
        if e.op == DELETION:
            return "delete"
        msg = f"Bad entry type: {e.type}"
        raise ValueError(msg)

    @property
    def entity_url(self) -> str | None:
        """Where the object is seen, if it still is and has a page of its own."""
        return None if self.entity_deleted else _url_or_none(self.entry.entity)

    def render(self) -> str:
        render = render_template_string
        e = self.entry
        user = self.render_user(e.user)
        entity_html = e.entity_name

        if self.entity_url:
            entity_html = Markup(
                render(
                    '<a href="{{ url }}">{{ entity.path or entity.name }}</a>',
                    url=self.entity_url,
                    entity=e.entity,
                )
            )

        msg = {
            "create": _('{user} created {entity_type} {entity_id} "{entity}"'),
            "update": _('{user} made changes on {entity_type} {entity_id} "{entity}"'),
            "delete": _('{user} has deleted {entity_type}: {entity_id} "{entity}"'),
        }[self.verb]

        self.msg = Markup(
            msg.format(
                user=user,
                entity=entity_html,
                entity_type=e.entity_type.rsplit(".", 1)[-1],
                entity_id=e.entity_id,
            )
        )
        tmpl = get_template_attribute("admin/_macros.html", "m_audit_entry")
        return tmpl(self)


class SecurityEntryPresenter(BaseEntryPresenter):
    #: A role given or taken, or permissions inherited or not.
    verb = "permissions"

    @property
    def object_url(self) -> str | None:
        """Where the object is seen, if there is one and it has a page."""
        return _url_or_none(self.entry.object) if self.entry.object else None

    def __init__(self, entry: SecurityAudit) -> None:
        assert isinstance(entry, SecurityAudit)
        super().__init__(entry.manager, entry.happened_at)
        self.entry = entry

    def render(self) -> str:
        render = render_template_string
        e = self.entry

        # `manager` is nullable for the same reason `user` is: a role granted
        # by the CLI or a migration has nobody who granted it.
        manager = render(
            '<img class="avatar" '
            'src="{{ user_photo_url(user=manager, size=16) }}" alt="" />{{ link }}',
            manager=e.manager,
            link=self.render_user(e.manager),
        )

        if self.entry.user:
            principal = self.render_user(self.entry.user)
        elif self.entry.group:
            principal = render(self._GROUP_FMT, group=self.entry.group)
        else:
            principal = ""

        entity = ""
        if e.object_id:
            entity_url = None
            entity_name = e.object_name
            if e.object:
                entity_name = getattr(e.object, "path", e.object.name)
                entity_url = url_for(e.object)

            entity = render(
                '{%- if url %}<a href="{{ url }}">{%- endif %}'
                "{{ name }}{%- if url %}</a>{%- endif %}",
                url=entity_url,
                name=entity_name,
            )

            match e.op:
                case e.SET_INHERIT:
                    msg = _("{manager} has activated inheritance on {entity}")
                case e.UNSET_INHERIT:
                    msg = _("{manager} has deactivated inheritance on {entity}")
                case e.GRANT:
                    msg = _(
                        '{manager} has given role "{role}" to {principal} on {entity}'
                    )
                case e.REVOKE:
                    msg = _(
                        '{manager} has revoked role "{role}" from {principal} on {entity}'
                    )
                case _:
                    msg = f"Invalid entity op: {e.op}"
                    raise Exception(msg)
        elif e.op == e.GRANT:
            msg = _('{manager} has given role "{role}" to {principal}')
        elif e.op == e.REVOKE:
            msg = _('{manager} has revoked role "{role}" from {principal}')
        else:
            msg = f"Invalid entity op: {e.op}"
            raise Exception(msg)

        self.msg = Markup(
            msg.format(manager=manager, principal=principal, role=e.role, entity=entity)
        )
        tmpl = get_template_attribute("admin/_macros.html", "m_security_entry")
        return tmpl(self)


def _url_or_none(obj: Entity) -> str | None:
    """`obj`'s page, or None for an object that has none."""
    try:
        return url_for(obj)
    except (BuildError, ValueError):
        return None
