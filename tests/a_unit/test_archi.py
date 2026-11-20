# Copyright (c) 2012-2024, Abilian SAS

"""
Ref/tuto:

- https://github.com/jwbargsten/pytest-archon
- https://xebia.com/blog/how-to-tame-your-python-codebase/
"""

from __future__ import annotations

from pytest_archon import archrule

# def test_models_should_not_import_flask() -> None:
#     (
#         archrule("models should not import flask")
#         .match("abilian.core.models.*")
#         .should_not_import("flask")
#         .check("abilian")
#     )


def test_core_should_not_import_sbe() -> None:
    (
        archrule("core should not import sbe")
        .match("abilian.core.*")
        .should_not_import("abilian.sbe")
        .check("abilian")
    )


# def test_core_should_not_import_web() -> None:
#     (
#         archrule("core should not import web")
#         .match("abilian.core.*")
#         .should_not_import("abilian.web")
#         .check("abilian")
#     )
