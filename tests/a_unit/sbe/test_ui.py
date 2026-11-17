# Copyright (c) 2012-2026, Abilian SAS

"""The helpers of the pages on the Abilian Design System."""

from __future__ import annotations

import pytest

from abilian.sbe.ui import ID_COLOURS, file_icon, icon, identity_class, initials


def test_an_icon_is_decorative_and_carries_its_classes() -> None:
    svg = icon("bell", "ads-icon sbe-check")

    assert svg.startswith("<svg")
    assert 'class="ads-icon sbe-check"' in svg
    assert 'aria-hidden="true"' in svg
    assert "CLASS_SLOT" not in svg


def test_an_unknown_icon_fails_at_render_time() -> None:
    with pytest.raises(KeyError):
        icon("no-such-icon")


@pytest.mark.parametrize("key", ["Claire Moreau", "", 0, 7, 1234])
def test_an_identity_colour_is_one_of_the_palette(key: str | int) -> None:
    n = int(identity_class(key).removeprefix("sbe-id-"))

    assert 1 <= n <= ID_COLOURS


def test_an_identity_colour_is_stable() -> None:
    assert identity_class("Claire Moreau") == identity_class("Claire Moreau")


def test_communities_created_one_after_the_other_differ() -> None:
    assert identity_class(41) != identity_class(42)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Claire Moreau", "CM"), ("Plato", "P"), ("jean de la Fontaine", "JD"), ("", "?")],
)
def test_initials(name: str, expected: str) -> None:
    assert initials(name) == expected


@pytest.mark.parametrize(
    ("name", "colour"),
    [
        ("Rapport.PDF", "sbe-filetype--pdf"),
        ("budget.ods", "sbe-filetype--sheet"),
        ("photo.jpeg", "sbe-filetype--image"),
    ],
)
def test_a_file_icon_takes_its_type_colour(name: str, colour: str) -> None:
    assert f'class="sbe-filetype {colour}"' in file_icon(name)


def test_a_file_of_unknown_type_has_the_plain_icon() -> None:
    assert file_icon("notes").startswith('<span class="sbe-filetype">')
