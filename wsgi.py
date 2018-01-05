# Run as a WSGI app

from __future__ import absolute_import, print_function, unicode_literals

from abilian.sbe.application import create_app

app = create_app()
