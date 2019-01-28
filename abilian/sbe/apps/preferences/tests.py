# coding=utf-8
from flask import url_for


def test_sbe_notifications(client, login_user, req_ctx):
    response = client.get(url_for("preferences.sbe_notifications"))
    assert response.status_code == 200
