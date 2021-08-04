"""
Test helpers.
"""
from typing import List

from abilian.services import get_service


def start_services(services: List[str]):
    for service_name in services:
        svc = get_service(service_name)
        svc.start()
