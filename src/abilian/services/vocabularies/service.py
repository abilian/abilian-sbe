# Copyright (c) 2012-2024, Abilian SAS

"""Vocabularies service."""

from __future__ import annotations

import typing
from inspect import isclass

import jinja2

from abilian.services.base import Service

from .models import BaseVocabulary

if typing.TYPE_CHECKING:
    from abilian.app import Application


def _vocabularies() -> set[type[BaseVocabulary]]:
    return {
        cls
        # for cls in BaseVocabulary.registry._class_registry.values().values()
        # for sqlalchemy 1.3.24:
        for cls in BaseVocabulary.registry._class_registry.values()
        if isclass(cls) and issubclass(cls, BaseVocabulary)
    }


def _grouped_vocabularies():
    by_group = {}
    for voc in sorted(_vocabularies(), key=lambda v: v.Meta.name):
        by_group.setdefault(voc.Meta.group, []).append(voc)
    return by_group


def get_vocabulary(name: str, group: str | None = "") -> type[BaseVocabulary] | None:
    name = name.lower()
    vocs = _grouped_vocabularies()
    for voc in vocs.get(group, ()):
        if voc.Meta.name == name:
            return voc

    return None


class VocabularyService(Service):
    name = "vocabularies"

    def init_app(self, app: Application) -> None:
        super().init_app(app)
        loader = jinja2.PackageLoader("abilian.services.vocabularies")
        app.register_jinja_loaders(loader)

    @property
    def vocabularies(self) -> set[type[BaseVocabulary]]:
        return _vocabularies()

    @property
    def grouped_vocabularies(self):
        return _grouped_vocabularies()

    def get_vocabulary(self, name: str, group: str | None = ""):
        return get_vocabulary(name, group=group)


vocabularies = VocabularyService()
