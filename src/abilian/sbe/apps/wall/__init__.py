from __future__ import annotations

from abilian.sbe.app import Application


def register_plugin(app: Application):
    from .views import wall

    app.register_blueprint(wall)
