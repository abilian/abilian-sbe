# Copyright (c) 2012-2024, Abilian SAS

"""The dashboard's aggregation, which is where its charts used to lie.

Five things went wrong before and are checked here: gaps in the series (a line
chart draws straight across them), weekly and monthly counts built by summing
daily ones (that counts a returning user once per visit), totals derived from
login history rather than from account creation, a series that stopped at the
last data point so a dead stretch looked like the end of time, and a trailing
part-period plotted beside whole ones.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from abilian.web.admin.panels.dashboard import (
    _epoch_seconds,
    _next_day,
    _next_month,
    _next_week,
    columns,
    unique_users,
    user_columns,
)

ALICE, BOB = 1, 2


def last_complete_month() -> date:
    """The month before the one we are in, which is the last one plotted."""
    this_month = datetime.now(UTC).date().replace(day=1)
    return (this_month - timedelta(days=1)).replace(day=1)


def by_date(series: list[list[int]]) -> dict[date, int]:
    """A [timestamps, values] pair, indexed by day for readable assertions."""
    stamps, values = series
    return {
        datetime.fromtimestamp(stamp, UTC).date(): value
        for stamp, value in zip(stamps, values, strict=True)
    }


def sessions_on(*days: tuple[str, int]) -> list[tuple[datetime, int]]:
    return [(datetime.fromisoformat(f"{day}T09:00"), user_id) for day, user_id in days]


def test_series_has_no_gaps() -> None:
    """Two logins a week apart yield a point for every day between them."""
    by_day, _week, _month = unique_users(
        sessions_on(("2024-03-01", ALICE), ("2024-03-08", ALICE))
    )
    counts = by_date(columns(by_day, date(2024, 3, 31), _next_day))

    assert counts[date(2024, 3, 1)] == 1
    assert counts[date(2024, 3, 8)] == 1
    assert [counts[date(2024, 3, n)] for n in range(2, 8)] == [0] * 6


def test_a_user_is_counted_once_per_period() -> None:
    """Alice on three days of one week is one unique connection that week."""
    by_day, by_week, by_month = unique_users(
        sessions_on(
            ("2024-03-04", ALICE),
            ("2024-03-05", ALICE),
            ("2024-03-06", ALICE),
            ("2024-03-06", BOB),
        )
    )

    assert by_day[date(2024, 3, 6)] == 2
    assert by_week[date(2024, 3, 4)] == 2  # not 4
    assert by_month[date(2024, 3, 1)] == 2


def test_weeks_start_on_monday() -> None:
    """A Sunday and the Monday after it fall in different weeks."""
    _day, by_week, _month = unique_users(
        sessions_on(("2024-03-03", ALICE), ("2024-03-04", ALICE))
    )

    assert sorted(by_week) == [date(2024, 2, 26), date(2024, 3, 4)]


def test_a_quiet_stretch_reads_as_zero() -> None:
    """The series runs to the present, so silence since 2020 is visible."""
    _day, _week, by_month = unique_users(sessions_on(("2020-06-15", ALICE)))
    counts = by_date(columns(by_month, _utc_today(), _next_month))

    assert counts[date(2020, 6, 1)] == 1
    assert counts[date(2020, 7, 1)] == 0
    assert max(counts) == last_complete_month()


def test_the_current_period_is_left_off() -> None:
    """It is still filling up, so plotting it ends every chart in a cliff."""
    today = _utc_today()
    by_day, by_week, _month = unique_users(
        [
            (datetime.now(UTC).replace(tzinfo=None), ALICE),
            *sessions_on(("2020-06-15", BOB)),
        ]
    )

    assert max(by_date(columns(by_day, today, _next_day))) == today - timedelta(days=1)
    assert max(by_date(columns(by_week, today, _next_week))) < today


def test_a_brand_new_site_still_gets_a_point() -> None:
    """Dropping the current period must not leave the chart empty on day one."""
    _day, _week, by_month = unique_users(
        [(datetime.now(UTC).replace(tzinfo=None), ALICE)]
    )
    stamps, values = columns(by_month, _utc_today(), _next_month)

    assert stamps == [_epoch_seconds(_utc_today().replace(day=1))]
    assert values == [1]


def test_no_data_is_an_empty_series() -> None:
    assert unique_users([]) == ({}, {}, {})
    assert columns({}, _utc_today(), _next_day) == [[], []]
    assert user_columns({}, {}, _utc_today()) == [[], [], [], []]


def test_the_three_user_series_share_one_grid() -> None:
    """uPlot draws them against a single x array, so they must be aligned."""
    stamps, registered, active, new = user_columns(
        {date(2024, 1, 1): 2, date(2024, 3, 1): 1},
        {date(2024, 2, 1): 1, date(2024, 3, 1): 2},
        date(2024, 5, 15),
    )

    assert len(stamps) == len(registered) == len(active) == len(new) == 4
    assert new == [2, 0, 1, 0]
    assert registered == [2, 2, 3, 3]  # a running total, never falling back
    assert active == [0, 1, 2, 0]


def test_growth_counts_accounts_that_never_logged_in() -> None:
    """A user created in a month with no logins still moves the total."""
    _stamps, registered, active, _new = user_columns(
        {date(2024, 1, 1): 3}, {}, date(2024, 3, 15)
    )

    assert registered == [3, 3]
    assert active == [0, 0]


def test_next_month_rolls_over_the_year() -> None:
    assert _next_month(date(2024, 12, 1)) == date(2025, 1, 1)
    assert _next_month(date(2024, 1, 1)) == date(2024, 2, 1)


def _utc_today() -> date:
    return datetime.now(UTC).date()
