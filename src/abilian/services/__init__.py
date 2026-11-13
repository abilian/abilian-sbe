# Copyright (c) 2012-2024, Abilian SAS

"""Modules that provide services.

They are implemented as Flask extensions (see:
http://flask.pocoo.org/docs/extensiondev/ )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload

from flask import current_app

from abilian.core.application import as_application

# This one must be imported first
from .base import Service, ServiceState

# Don't remove (used to force import order)
assert Service, ServiceState

# flake8: noqa
# Import below are flagged as problematic due to the trick above.


if TYPE_CHECKING:
    from .antivirus.service import AntiVirusService
    from .indexing.service import WhooshIndexService
    from .preferences.service import PreferenceService
    from .security.service import SecurityService
    from .settings.service import SettingsService
    from .vocabularies.service import VocabularyService


# One overload per service looked up by name, so callers get its methods.
@overload
def get_service(service: Literal["antivirus"]) -> AntiVirusService: ...
@overload
def get_service(service: Literal["indexing"]) -> WhooshIndexService: ...
@overload
def get_service(service: Literal["preferences"]) -> PreferenceService: ...
@overload
def get_service(service: Literal["security"]) -> SecurityService: ...
@overload
def get_service(service: Literal["settings"]) -> SettingsService: ...
@overload
def get_service(service: Literal["vocabularies"]) -> VocabularyService: ...
@overload
def get_service(service: str) -> Service: ...
def get_service(service: str) -> Service:
    return as_application(current_app).service_manager.get_service(service)


from .activity import ActivityService
from .antivirus import service as antivirus
from .audit import audit_service
from .auth import AuthService
from .blob_store import blob_store, session_blob_store
from .conversion import conversion_service, converter
from .indexing import service as index_service
from .preferences import preferences as preferences_service
from .security import security as security_service
from .settings import SettingsService
from .vocabularies import vocabularies as vocabularies_service

auth_service = AuthService()
activity_service = ActivityService()
settings_service = SettingsService()


def get_security_service():
    return security_service
