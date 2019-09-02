from flask import Blueprint

notifications = Blueprint(
    "notifications",
    __name__,
    url_prefix="/notifications",
    template_folder="../templates",
)
