# Copyright (c) 2012-2024, Abilian SAS

"""Singleton for Dramatiq task manager, to permit lazy declaration of actors."""

from __future__ import annotations

from flask_dramatiq import Dramatiq

dramatiq = Dramatiq()

# Remove prometheus from middleware list if present (default in dramatiq 1.x)
# See:
# https://groups.io/g/dramatiq-users/topic/disabling_prometheus/80745532?p=
dramatiq.middleware = [
    m for m in dramatiq.middleware if type(m).__name__ != "Prometheus"
]
