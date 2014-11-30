"""Main views.
"""

from flask import render_template, Blueprint

__all__ = []

blueprint = Blueprint("main", __name__, url_prefix="")
route = blueprint.route


#
# Basic navigation
#
@route("/")
def home():
  return render_template("index.html")


# TODO
# @route("/help/")
# def help():
#   return render_template('help.html')
#
