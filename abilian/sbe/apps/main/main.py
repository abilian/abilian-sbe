"""Main views.
"""

from flask import render_template, Blueprint, redirect, g

from abilian.services.security import security


__all__ = []

blueprint = Blueprint("main", __name__, url_prefix="")
route = blueprint.route

#
# Basic navigation
#
@route("/")
def home():
  return render_template("index.html")


@route("/help/")
def help():
  return render_template('help.html')

