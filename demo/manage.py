#!./bin/python
# coding=utf-8
"""
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

from abilian.core.commands import setup_abilian_commands
from flask_script import Manager

from abilian.sbe.app import Application


def create_app():
    app = Application(name='sbe-demo')
    return app


if __name__ == '__main__':
    logging.basicConfig()
    manager = Manager(create_app)
    setup_abilian_commands(manager)

    manager.run()
