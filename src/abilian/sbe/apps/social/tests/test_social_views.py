from flask import url_for


def test_home(client, login_admin):
    response = client.get(url_for("social.home"))
    assert response.status_code == 200


def test_users(client, login_admin):
    response = client.get(url_for("social.users"))
    assert response.status_code == 200


def test_groups(client, login_admin):
    response = client.get(url_for("social.groups"))
    assert response.status_code == 200


def test_user(client, login_admin):
    user = login_admin
    response = client.get(url_for("social.user", user_id=user.id))
    assert response.status_code == 200
