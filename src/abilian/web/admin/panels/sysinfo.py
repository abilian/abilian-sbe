# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import distributions
from operator import itemgetter

from flask import current_app, render_template

from abilian.web.admin import AdminPanel


def installed_packages() -> list[dict[str, str]]:
    packages = [
        {"name": d.name.lower(), "version": d.version, "metadata": {}}
        for d in distributions()
    ]
    return sorted(packages, key=itemgetter("name"))


class SysinfoPanel(AdminPanel):
    id = "sysinfo"
    label = "System information"
    icon = "hdd-o"

    def get(self) -> str:
        uname = subprocess.check_output(["uname", "-a"]).decode().strip()
        python_version = sys.version.strip()

        packages = installed_packages()

        config_values = [(k, repr(v)) for k, v in sorted(current_app.config.items())]

        ctx = {
            "python_version": python_version,
            "packages": packages,
            "uname": uname,
            "config_values": config_values,
        }
        return render_template("admin/sysinfo.html", **ctx)
