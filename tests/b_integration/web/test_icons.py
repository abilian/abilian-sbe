# Copyright (c) 2012-2024, Abilian SAS

""""""

from __future__ import annotations

from abilian.web.action import FAIcon, Glyphicon, StaticIcon


def test_glyphicons() -> None:
    # Glyphicon is deprecated and now renders as FAIcon; kept so existing
    # callers keep working during the Bootstrap -> Tailwind migration.
    icon = Glyphicon("ok")
    assert icon.__html__() == '<i class="fa fa-ok"></i>'
    assert icon.__html__() == FAIcon("ok").__html__()


def test_faicons() -> None:
    icon = FAIcon("check")
    assert icon.__html__() == '<i class="fa fa-check"></i>'


def test_staticicon(app) -> None:
    with app.test_request_context():
        icon = StaticIcon("path/to/icon.png")
        assert (
            icon.__html__()
            == '<img src="/static/path/to/icon.png" alt="" width="12" height="12" />'
        )

        icon = StaticIcon("path/to/icon.png", width=14)
        assert (
            icon.__html__()
            == '<img src="/static/path/to/icon.png" alt="" width="14" height="12" />'
        )

        icon = StaticIcon("path/to/icon.png", height=14)
        assert (
            icon.__html__()
            == '<img src="/static/path/to/icon.png" alt="" width="12" height="14" />'
        )

        icon = StaticIcon("path/to/icon.png", size=14)
        assert (
            icon.__html__()
            == '<img src="/static/path/to/icon.png" alt="" width="14" height="14" />'
        )

        icon = StaticIcon("path/to/icon.png", size=14, css="avatar")
        assert (
            icon.__html__()
            == '<img class="avatar" src="/static/path/to/icon.png" alt="" width="14" '
            'height="14" />'
        )


def test_static_url_with_csrf(app, client, monkeypatch) -> None:
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)
    response = client.get("/static/abilian/img/logo-abilian-32x32.png")
    assert response.status_code == 200
    response.close()
