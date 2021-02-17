"""Static configuration for the application.

TODO: add more (runtime) flexibility in plugin discovery, selection
and activation.

NB: not used anymore.
"""
import logging
import os
import subprocess
import sys
from pathlib import Path

from flask import current_app
from werkzeug.serving import BaseWSGIServer

# SBE demo app bootstrap stuff
_SBE_DEMO_SCRIPT = """\
#!{BIN_DIR}/python
from __future__ import absolute_import

import sys
from abilian.sbe.app import command_entry_point

sys.exit(command_entry_point())
"""

_BASE_SERVER_ACTIVATE = BaseWSGIServer.server_activate


def _on_http_server_activate(self, *args, **kwargs):
    """This function is used as to monkey patch BaseWSGIServer.server_activate
    during `setup_sbe_demo`."""
    _BASE_SERVER_ACTIVATE(self)
    # now we are listening to socket
    host, port = self.server_address
    if host == "0.0.0.0":
        # chrome is not ok with 0.0.0.0
        host = "localhost"
    url = f"http://{host}:{port}/setup"

    if sys.platform == "win32":
        os.startfile(url)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, url])


# run with python -m abilian.sbe.app setup_sbe_app
def setup_sbe_app():
    """Basic set up SBE application. Must be run inside a virtualenv.

    Will create `abilian_sbe` script, run a local server and open
    browser on app's setup wizard.
    """
    logger = logging.getLogger("sbe_demo")
    logger.setLevel(logging.INFO)

    if "VIRTUAL_ENV" not in os.environ:
        logger.error("Not in a virtualenv! Aborting.")
        return 1

    bin_dir = Path(sys.prefix) / "bin"

    if not bin_dir.exists() or not bin_dir.is_dir():
        logger.error("%s doesn't exists or is not a directory. Aborting", bin_dir)
        return 1

    script_file = bin_dir / "abilian_sbe"
    if script_file.exists():
        logger.info("%s already exists. Skipping creation.", script_file)
    else:
        with script_file.open("w") as out:
            logger.info('Create script: "%s".', script_file)
            content = _SBE_DEMO_SCRIPT.format(BIN_DIR=bin_dir)
            out.write(content)
        # 0755: -rwxr-xr-x
        script_file.chmod(0o755)

    current_app.config["PRODUCTION"] = True
    current_app.config["DEBUG"] = False
    current_app.config["ASSETS_DEBUG"] = False
    current_app.config["SITE_NAME"] = "Abilian SBE"
    current_app.config["MAIL_SENDER"] = "abilian-sbe-app@example.com"

    logger.info("Prepare CSS & JS files")
    # command_manager.handle("abilian_sbe", ["assets", "build"])
    # disabled init config: only if not running setupwizard
    # command_manager.handle('abilian_sbe', ['config', 'init'])

    # patch server used to launch browser here immediately after socket opened
    BaseWSGIServer.server_activate = _on_http_server_activate
    return
    # return command_manager.handle("abilian_sbe", ["run", "--hide-config"])


def command_entry_point():
    pass
    # command_manager.run(commands={"setup_sbe_app": Command(setup_sbe_app)})


if __name__ == "__main__":
    command_entry_point()
