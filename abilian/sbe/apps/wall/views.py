from flask import g, render_template

from abilian.sbe.apps.communities.blueprint import Blueprint

from .util import get_recent_entries
from .presenters import ActivityEntryPresenter


wall = Blueprint("wall", __name__,
                 url_prefix="/wall",
                 template_folder="templates")
route = wall.route


@wall.url_value_preprocessor
def set_current_tab(endpoint, values):
  g.current_tab = 'wall'


@route('')
def index():
  entries = get_recent_entries(20, community=g.community)
  entries = ActivityEntryPresenter.wrap_collection(entries)
  return render_template("wall/index.html", entries=entries)
