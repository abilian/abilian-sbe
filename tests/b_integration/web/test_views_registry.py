# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

import sqlalchemy as sa
from flask import Blueprint, Flask
from pytest import fixture, raises

from abilian.core.entities import Entity

# needed if running only this test, else SA won't have registered this mapping
# required by Entity.owner_id, etc
# noinspection PyUnresolvedReferences
from abilian.web.views import default_view
from abilian.web.views.registry import Registry
from tests.util import class_fqn


class RegEntity(Entity):
    name = sa.Column(sa.Unicode, default="")


class RegEntity2(Entity):
    name = sa.Column(sa.Unicode, default="")


class RegEntity3(Entity):
    name = sa.Column(sa.Unicode, default="")


class RegEntity4(Entity):
    name = sa.Column(sa.Unicode, default="")


class RegEntity5(Entity):
    name = sa.Column(sa.Unicode, default="")


@fixture
def registry(app: Flask) -> Registry:
    app.default_view = Registry()
    return app.default_view


def test_register_class(app: Flask, registry: Registry) -> None:
    registry.register(RegEntity, lambda ignored: "")
    assert RegEntity.entity_type in registry._map

    # def test_register_instance(app: Flask, registry: Registry):
    obj = RegEntity2()
    registry.register(obj, lambda ignored: "")
    assert RegEntity2.entity_type in registry._map

    # def test_custom_url_func(app: Flask, registry: Registry):
    name = "obj"
    obj = RegEntity3(id=1, name=name)

    def custom_url(obj: RegEntity3, obj_type: str, obj_id: int) -> str:
        return obj.name

    registry.register(obj, custom_url)
    assert registry.url_for(obj) == name

    def url_from_type_and_id(obj: RegEntity3, obj_type: str, obj_id: int) -> str:
        return f"{obj_type}:{obj_id}"

    registry.register(obj, url_from_type_and_id)
    assert registry.url_for(obj) == f"{class_fqn(RegEntity3)}:1"

    # def test_default_url_func(app: Flask, registry: Registry):
    obj = RegEntity4(id=2)

    @app.route("/regentities_path/<int:object_id>/view", endpoint="regentity4.view")
    def dummy_default_view(object_id) -> None:
        pass

    assert registry.url_for(obj) == "/regentities_path/2/view"
    assert (
        registry.url_for(obj, _external=True)
        == "http://localhost.localdomain/regentities_path/2/view"
    )

    # def test_default_view_decorator(app: Flask, registry: Registry):
    bp = Blueprint("registry", __name__, url_prefix="/blueprint")

    @default_view(bp, RegEntity5)
    @bp.route("/<int:object_id>")
    def view(object_id) -> None:
        pass

    obj = RegEntity5(id=3)
    # blueprint not registered: no rule set
    with raises(KeyError):
        registry.url_for(obj)

    # blueprint registered: default view is set
    app.register_blueprint(bp)

    assert registry.url_for(obj) == "/blueprint/3"
    assert (
        registry.url_for(obj, _external=True)
        == "http://localhost.localdomain/blueprint/3"
    )
