# Note: this test suite is using pytest instead of the unittest-based scaffolding
# provided by SBE. Hopefully one day all of SBE will follow.

from datetime import datetime, timedelta
from typing import Iterator, Union

import pytest

import abilian.i18n
from abilian.core.signals import activity
from abilian.sbe.app import Application, create_app
from abilian.sbe.apps.communities.common import activity_time_format


@pytest.fixture
def app(config: type) -> Iterator[Union[Iterator, Iterator[Application]]]:
    app = create_app(config)

    # We need some incantations here to make babel work in the test
    babel = abilian.i18n.babel
    babel.locale_selector_func = None

    yield app

    # Signals are globals and apparently need to be cleaned up.
    # At this point, only the "activity" signal seems to have a side effect.
    activity._clear_state()


def test_activity_time_format(app: Application) -> None:
    # We need the app context because of Babel.

    with app.app_context():
        then = datetime(2017, 1, 1, 12, 0, 0)

        now = then + timedelta(0, 5)
        assert activity_time_format(then, now) == "5s"

        now = then + timedelta(0, 5 * 60)
        assert activity_time_format(then, now) == "5m"

        now = then + timedelta(0, 5 * 60 * 60)
        assert activity_time_format(then, now) == "5h"

        now = then + timedelta(1, 5)
        assert activity_time_format(then, now) == "1d"

        now = then + timedelta(60, 5)
        assert activity_time_format(then, now) == "Jan 1"

        now = then + timedelta(365 + 60, 5)
        assert activity_time_format(then, now) == "Jan 2017"
