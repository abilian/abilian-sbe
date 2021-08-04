"""
Test helpers.
"""
from __future__ import annotations

from typing import List

from abilian.services import get_service


def start_services(services: list[str]):
    for service_name in services:
        svc = get_service(service_name)
        svc.start()
