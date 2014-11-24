#!/usr/bin/env python

from __future__ import absolute_import
from sqlalchemy.exc import IntegrityError
from abilian.core.extensions import db
from abilian.core.commands.base import initdb, createadmin, run
from abilian.sbe.app import Application

app = Application(name='myapp')

import testliveserver
testliveserver.Flask.wrap(app)

with app.app_context():
  initdb()
  try:
    createadmin("admin@example.com", "admin")
  except IntegrityError:
    db.session.rollback()
  run()
