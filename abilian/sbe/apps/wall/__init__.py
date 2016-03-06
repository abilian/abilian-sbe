def register_plugin(app):
    from .views import wall
    app.register_blueprint(wall)
