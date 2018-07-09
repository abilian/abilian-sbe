# coding=utf-8
# Run as a WSGI app

from __future__ import absolute_import, print_function, unicode_literals

from abilian.sbe.app import Application

app = Application(name="sbe-demo")
