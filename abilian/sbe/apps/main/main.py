"""Main views."""

from __future__ import absolute_import, print_function, unicode_literals

from flask import Blueprint, render_template

__all__ = ()

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
