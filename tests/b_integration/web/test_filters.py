# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import datetime as dt
from textwrap import dedent
from typing import TYPE_CHECKING

from flask import Flask
from flask_babel import Babel
from jinja2 import Environment
from pytest import fixture
from pytz import timezone, utc

from abilian.web import filters

if TYPE_CHECKING:
    from collections.abc import Iterator

NNSP = "\u202f"  # narrow no-break space

env = Environment()
filters.init_filters(env)


def en_locale() -> str:
    return "en"


def user_tz() -> str:
    # This one is GMT+8 and has no DST (tests should pass any time in year)
    return "Asia/Hong_Kong"


USER_TZ = timezone(user_tz())


def test_filesize() -> None:
    filesize = filters.filesize
    assert str(filesize("100")) == f"100{NNSP}B"
    assert str(filesize(100)) == f"100{NNSP}B"
    assert str(filesize(1000)) == f"1.0{NNSP}kB"
    assert str(filesize(1100)) == f"1.1{NNSP}kB"
    assert str(filesize(10000)) == f"10{NNSP}kB"
    assert str(filesize(1100100)) == f"1.1{NNSP}MB"
    assert str(filesize(10000000)) == f"10{NNSP}MB"
    assert str(filesize(1100100000)) == f"1.1{NNSP}GB"
    assert str(filesize(100000000000)) == f"100{NNSP}GB"


def test_paragraphs() -> None:
    markdown_text = dedent(
        """\
        {{ "First paragraph
        some text
        with line return

        Second paragraph
        ... lorem

        Last one - a single line" | paragraphs }}
        """
    )
    tmpl = env.from_string(markdown_text)

    expected = dedent(
        """\
        <p>First paragraph<br />
        some text<br />
        with line return</p>

        <p>Second paragraph<br />
        ... lorem</p>

        <p>Last one - a single line</p>
        """
    )
    assert tmpl.render().strip() == expected.strip()


@fixture
def app() -> Iterator[Flask]:
    app = Flask(__name__)
    babel = Babel(app, default_locale="fr", default_timezone=USER_TZ)
    babel.localeselector(en_locale)
    babel.timezoneselector(user_tz)
    with app.app_context():
        yield app


def test_age(app: Flask) -> None:
    age = filters.age
    now = dt.datetime(2012, 6, 10, 10, 10, 10, tzinfo=utc)
    d1m = dt.datetime(2012, 6, 10, 10, 10, 0, tzinfo=utc)
    d3w = dt.datetime(2012, 5, 18, 8, 0, 0, tzinfo=utc)
    d2011 = dt.datetime(2011, 9, 4, 12, 12, 0, tzinfo=utc)

    # default parameters
    assert age(None) == ""
    assert age(d1m, now) == "1 minute ago"
    assert age(d3w, now) == "3 weeks ago"

    # with direction
    assert age(d1m, now, add_direction=False) == "1 minute"
    assert age(d3w, now, add_direction=False) == "3 weeks"

    # with date_threshold
    assert age(d1m, now, date_threshold="day") == "1 minute ago"

    # same year: 2012 not shown
    assert age(d3w, now, date_threshold="day") == f"May 18, 4:00{NNSP}PM"
    # different year: 2011 shown
    assert age(d2011, now, date_threshold="day") == f"September 4, 2011, 8:12{NNSP}PM"

    # using default parameter now=None
    # dt_patcher = mock.patch.object(
    #     datetime, "datetime", mock.Mock(wraps=datetime.datetime)
    # )
    # with dt_patcher as mocked:
    #     mocked.utcnow.return_value = now
    #     assert age(d1m) == "1 minute ago"
