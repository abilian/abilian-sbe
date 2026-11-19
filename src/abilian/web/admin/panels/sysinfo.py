# Copyright (c) 2012-2024, Abilian SAS

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import distributions
from operator import itemgetter

from flask import current_app, render_template

from abilian.i18n import _l
from abilian.web.admin import AdminPanel

#: What a setting's name holds when its value is a secret: a key, a password, or
#: an address that may carry one (a database's, a broker's).
SECRET_MARKS = ("SECRET", "PASSWORD", "TOKEN", "KEY", "URI")

#: What the page shows in a secret's place.
HIDDEN = "••••••••"


def is_secret(name: str) -> bool:
    """Whether a setting's value must not be shown, even to an administrator."""
    return any(mark in name.upper() for mark in SECRET_MARKS)


def installed_packages() -> list[dict[str, str]]:
    packages = [
        {"name": d.name.lower(), "version": d.version, "metadata": {}}
        for d in distributions()
    ]
    return sorted(packages, key=itemgetter("name"))


class SysinfoPanel(AdminPanel):
    id = "sysinfo"
    label = _l("System information")
    icon = "hdd-o"

    def get(self) -> str:
        uname = subprocess.check_output(["uname", "-a"]).decode().strip()
        python_version = sys.version.strip()

        packages = installed_packages()

        config_values = [
            (k, HIDDEN if is_secret(k) else repr(v))
            for k, v in sorted(current_app.config.items())
        ]

        ctx = {
            "python_version": python_version,
            "packages": packages,
            "uname": uname,
            "config_values": config_values,
        }
        return render_template("admin/sysinfo.html", **ctx)
