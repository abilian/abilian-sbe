# Copyright (c) 2026, Abilian SAS

"""The screenshots on the documentation site, taken from a throwaway instance.

    make shots                              # from docs/: both languages
    uv run --project .. --with playwright python shots.py fr    # one language

For each language: a fresh SQLite database and instance under a temporary
directory, its own Redis on a free port, `flask initdb`, the demo data
(demo.py), the search index, then `flask run`. Playwright signs in as the demo
coordinator, whose interface is in that language, and photographs each page
into src/assets/shots/<lang>/. Nothing touches a development database or the
default Redis.

The pages are the app as a user sees it: the data is invented, the interface
is not. Regenerate after anything that changes how a page looks.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "src" / "assets" / "shots"
LANGS = ("en", "fr")
VIEWPORT = {"width": 1360, "height": 860}
SITE_NAME = {"en": "Libre Cluster", "fr": "Pôle Libre"}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def pages(demo: dict) -> dict[str, str]:
    """Each screenshot's name, and the page it shows."""
    board = f"/communities/{demo['communities']['board']}"
    return {
        "home": "/",
        "community": f"{board}/wall/",
        "discussions": f"{board}/forum/",
        "thread": f"{board}/forum/{demo['thread']}/",
        "documents": f"{board}/docs/",
        "document": f"{board}/docs/doc/{demo['document']}",
        "wiki": f"{board}/wiki/page/?title={demo['wiki']}",
        "calendar": f"{board}/calendar/",
        "members": f"{board}/members",
        "communities": "/communities/",
        "discover": "/communities/discover/",
        "directory": "/social/users/",
        "search": "/search?q=budget",
        "account": "/preferences/",
    }


def wait_for(port: int, seconds: int = 60) -> None:
    """Until the server accepts connections on `port`."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return
        except OSError:
            time.sleep(0.5)
    msg = f"nothing answered on port {port} within {seconds}s"
    raise SystemExit(msg)


def shoot(lang: str) -> None:
    work = Path(tempfile.mkdtemp(prefix=f"sbe-shots-{lang}-"))
    redis_port, web_port = free_port(), free_port()
    env = os.environ | {
        "FLASK_DEBUG": "0",
        "FLASK_SECRET_KEY": "shots-secret",
        "FLASK_SQLALCHEMY_DATABASE_URI": f"sqlite:///{work}/shots.db",
        "FLASK_INSTANCE_PATH": str(work / "instance"),
        "FLASK_REDIS_URI": f"redis://localhost:{redis_port}/0",
        "FLASK_DRAMATIQ_BROKER_URL": f"redis://localhost:{redis_port}/0",
        "FLASK_SERVER_NAME": f"127.0.0.1:{web_port}",
        "FLASK_TALISMAN_FORCE_HTTPS": "false",
        "FLASK_MAIL_SUPPRESS_SEND": "1",
        "FLASK_MAIL_SENDER": "demo@example.org",
        "FLASK_SITE_NAME": SITE_NAME[lang],
        "FLASK_BABEL_DEFAULT_LOCALE": lang,
        "DEMO_LANG": lang,
        "DEMO_OUT": str(work / "demo.json"),
    }
    redis = subprocess.Popen(
        ["redis-server", "--port", str(redis_port), "--save", "", "--dir", str(work)],
        stdout=subprocess.DEVNULL,
    )
    web = None
    try:
        flask = ["uv", "run", "--project", str(ROOT), "flask"]
        for args in (["initdb"], ["script", "docs/demo.py"], ["reindex"]):
            subprocess.run(flask + args, env=env, cwd=ROOT, check=True)
        demo = json.loads((work / "demo.json").read_text("utf-8"))
        web = subprocess.Popen(
            [*flask, "run", "--port", str(web_port), "--host", "127.0.0.1"],
            env=env,
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
        base = f"http://127.0.0.1:{web_port}"
        wait_for(web_port)
        out = SHOTS / lang
        out.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport=VIEWPORT, locale=lang)
            page.goto(f"{base}/user/login")
            page.screenshot(path=out / "login.png")
            sign_in(page, demo["email"], demo["password"])
            for name, path in pages(demo).items():
                page.goto(f"{base}{path}", wait_until="networkidle")
                page.screenshot(path=out / f"{name}.png")
                print(f"{lang}/{name}.png")
            # The administration, as the site's administrator sees it.
            admin = browser.new_page(viewport=VIEWPORT, locale=lang)
            admin.goto(f"{base}/user/login")
            sign_in(admin, demo["admin"], demo["password"])
            admin.goto(f"{base}/admin/dashboard", wait_until="networkidle")
            admin.screenshot(path=out / "admin.png")
            browser.close()
    finally:
        if web:
            web.terminate()
            web.wait()
        redis.terminate()
        redis.wait()
        shutil.rmtree(work, ignore_errors=True)


def sign_in(page: Page, email: str, password: str) -> None:
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    with page.expect_navigation():
        page.locator('form button[type="submit"]').first.click()


def main() -> None:
    for lang in sys.argv[1:] or LANGS:
        shoot(lang)


if __name__ == "__main__":
    main()
