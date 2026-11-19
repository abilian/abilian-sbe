# Copyright (c) 2012-2024, Abilian SAS

"""Admin dashboard: what the site depends on, user growth and connection activity.

The charts are drawn by uPlot, which wants columnar data -- one shared array of
timestamps per chart, then one array of values per series -- so that is the
shape built here, rather than leaving the browser to reshape a list of points.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from itertools import accumulate
from typing import TYPE_CHECKING

import sqlalchemy as sa
from flask import render_template

from abilian.core.extensions import db
from abilian.core.models.subjects import ROOT_USER_ID, User
from abilian.i18n import _, _l
from abilian.services.audit import CREATION, AuditEntry
from abilian.services.auth.models import LoginSession
from abilian.web.admin import AdminPanel
from abilian.web.admin.panels.health import site_health

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping


#: How many of the last people to sign in the dashboard shows.
LAST_SEEN = 5


class DashboardPanel(AdminPanel):
    id = "dashboard"
    path = ""
    label = _l("Dashboard")
    icon = "eye"

    def get(self) -> str:
        # Two columns, one query. The aggregation below is plain Python, so
        # there is no reason to hydrate LoginSession rows and then lazy-load
        # `.user` on each of them -- which is what this did before, one SELECT
        # per session, on every dashboard load.
        sessions = (
            db.session.query(LoginSession.started_at, LoginSession.user_id)
            .filter(LoginSession.user_id != ROOT_USER_ID)
            .all()
        )
        signups = (
            db.session.query(User.created_at)
            .filter(User.id != ROOT_USER_ID, User.created_at.is_not(None))
            .all()
        )

        today = _utc_today()
        by_day, by_week, by_month = unique_users(sessions)
        new_per_month = Counter(
            _month_start(created_at.date()) for (created_at,) in signups
        )

        # Colours are set here and nowhere else. These are slots 1-3 of the
        # categorical palette, validated for colour-vision deficiency and for
        # >= 3:1 contrast on white. The pairing they replace -- green and orange
        # -- is precisely the one a deuteranope cannot separate.
        users = {
            "x_label": _("Date"),
            "data": user_columns(new_per_month, by_month, today),
            "series": [
                {"label": _("Registered"), "stroke": "#2a78d6"},
                {"label": _("Active"), "stroke": "#eb6834"},
                {"label": _("Newcomers"), "stroke": "#4a3aa7"},
            ],
        }
        # One measure at three resolutions: a granularity switch, not three
        # series to overlay. Weekly leads because it is the default view --
        # eleven years of daily points is a hairball.
        connections = {
            "x_label": _("Date"),
            "label": _("Connections"),
            "stroke": "#0053c1",
            "grains": [
                {"label": _("Weekly"), "data": columns(by_week, today, _next_week)},
                {"label": _("Daily"), "data": columns(by_day, today, _next_day)},
                {"label": _("Monthly"), "data": columns(by_month, today, _next_month)},
            ],
        }

        stats = {
            "today": stats_since(timedelta(days=1)),
            "this_week": stats_since(timedelta(days=7)),
            "this_month": stats_since(timedelta(days=30)),
        }

        month_ago = datetime.utcnow() - timedelta(days=30)
        this_month = [
            user_id for started_at, user_id in sessions if started_at > month_ago
        ]
        everyone = User.query.filter(User.id != ROOT_USER_ID)
        accounts = {
            "all": everyone.count(),
            "never_signed_in": everyone.filter(User.last_active.is_(None)).count(),
            "sign_ins": len(this_month),
            "people": len(set(this_month)),
        }
        last_seen = (
            everyone.filter(User.last_active.is_not(None))
            .order_by(User.last_active.desc())
            .limit(LAST_SEEN)
            .all()
        )

        return render_template(
            "admin/dashboard.html",
            health=site_health(),
            stats=stats,
            users=users,
            connections=connections,
            accounts=accounts,
            last_seen=last_seen,
        )


def stats_since(dt: timedelta) -> dict[str, int]:
    new_members = new_documents = new_messages = 0
    after_date = datetime.utcnow() - dt
    session = db.session()
    counts_per_type = (
        session.query(
            AuditEntry.entity_type.label("type"),
            sa.func.count(AuditEntry.entity_type).label("count"),
        )
        .group_by(AuditEntry.entity_type)
        .filter(AuditEntry.happened_at > after_date)
        .filter(AuditEntry.type == CREATION)
        .all()
    )

    for entity_type, count in counts_per_type:
        entity_class = entity_type.split(".")[-1]
        match entity_class:
            case "User":
                new_members = count
            case "Document":
                new_documents = count
            case "Message":
                new_messages = count

    active_users = (
        session.query(sa.func.count(User.id))
        .filter(User.last_active > after_date)
        .scalar()
    )

    return {
        "new_members": new_members,
        "active_users": active_users,
        "new_documents": new_documents,
        "new_messages": new_messages,
    }


def unique_users(
    sessions: Iterable[tuple[datetime, int]],
) -> tuple[dict[date, int], dict[date, int], dict[date, int]]:
    """Distinct users who connected, per day, per week and per month.

    Every grain is counted from the raw sessions. Summing the daily counts into
    a week -- which is what this used to do -- counts a user once per day they
    showed up, and that is not what "unique connections per week" means.
    """
    daily: dict[date, set[int]] = defaultdict(set)
    weekly: dict[date, set[int]] = defaultdict(set)
    monthly: dict[date, set[int]] = defaultdict(set)

    for started_at, user_id in sessions:
        day = started_at.date()
        daily[day].add(user_id)
        weekly[_week_start(day)].add(user_id)
        monthly[_month_start(day)].add(user_id)

    return (_sizes(daily), _sizes(weekly), _sizes(monthly))


def user_columns(
    new_per_month: Mapping[date, int],
    active_per_month: Mapping[date, int],
    through: date,
) -> list[list[int]]:
    """`[timestamps, registered, active, new]` on one shared grid of months.

    New users are counted from `User.created_at`, not from the date of a first
    login: an account that was created and never used is still an account, and
    the login-based version left those out of the totals entirely. Registered is
    the running total of that, so it can only rise.
    """
    known = [*new_per_month, *active_per_month]
    if not known:
        return [[], [], [], []]

    months = _periods(min(known), through, _next_month)
    new = [new_per_month.get(month, 0) for month in months]
    return [
        [_epoch_seconds(month) for month in months],
        list(accumulate(new)),
        [active_per_month.get(month, 0) for month in months],
        new,
    ]


def columns(
    counts: Mapping[date, int],
    through: date,
    next_period: Callable[[date], date],
) -> list[list[int]]:
    """`[timestamps, values]` for one grain, with no period missing."""
    if not counts:
        return [[], []]

    periods = _periods(min(counts), through, next_period)
    return [
        [_epoch_seconds(period) for period in periods],
        [counts.get(period, 0) for period in periods],
    ]


def _periods(
    first: date, through: date, next_period: Callable[[date], date]
) -> list[date]:
    """Every period start from `first` up to `through`, with none left out.

    The gaps are the point. A period with no data still gets its slot, so that
    "nobody connected" is distinguishable from "no sample here" -- otherwise a
    line is drawn straight across the silence, and an index-based x axis quietly
    squeezes eleven years of history into evenly spaced points.

    The period `through` falls in is left off: it is still filling up, and its
    count is not comparable with the completed ones beside it. Plotted, it ends
    every chart in a cliff that belongs to the calendar rather than to the data.
    Today's own figures belong on the stat tiles, which is where they are.
    """
    periods = []
    period = first
    while period <= through:
        periods.append(period)
        period = next_period(period)

    if len(periods) > 1 and next_period(periods[-1]) > through:
        periods.pop()
    return periods


def _sizes(buckets: Mapping[date, set[int]]) -> dict[date, int]:
    return {period: len(users) for period, users in buckets.items()}


EPOCH = date(1970, 1, 1)


def _utc_today() -> date:
    """Today in UTC -- the timezone the timestamps in the database are in."""
    return datetime.now(UTC).date()


def _epoch_seconds(day: date) -> int:
    """Midnight UTC on `day`, in the seconds uPlot's time axis expects."""
    return (day - EPOCH).days * 86_400


def _week_start(day: date) -> date:
    """The Monday of the week `day` falls in."""
    return day - timedelta(days=day.weekday())


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _next_day(day: date) -> date:
    return day + timedelta(days=1)


def _next_week(day: date) -> date:
    return day + timedelta(days=7)


def _next_month(day: date) -> date:
    return date(day.year + day.month // 12, day.month % 12 + 1, 1)
