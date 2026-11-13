#!/bin/sh
# Boot a throwaway Abilian SBE instance for the Playwright suite.
#
# Everything lives under $E2E_DIR and the database is recreated on every run, so
# this never touches a development database or the default Redis. Started by the
# Procfile next to this script; not meant to be run by hand.
set -e

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

: "${E2E_DIR:=/tmp/abilian-sbe-e2e}"
# `make test-e2e` picks free ports and exports them (see pick-ports.sh); these
# defaults are only for a bare `honcho start`.
: "${E2E_PORT:=8899}"
: "${E2E_REDIS_PORT:=6399}"
: "${E2E_EMAIL:=admin@example.com}"
: "${E2E_PASSWORD:=e2e-password}"

mkdir -p "$E2E_DIR"

# The repo's .env is auto-loaded and usually sets FLASK_DEBUG=true. Force it off:
# debug mode points vite_asset at a dev server that is not running here, and the
# built assets are exactly what we want these tests to exercise.
export FLASK_DEBUG=0
export FLASK_SECRET_KEY=e2e-secret
export FLASK_SQLALCHEMY_DATABASE_URI="sqlite:///$E2E_DIR/e2e.db"
export FLASK_REDIS_URI="redis://localhost:$E2E_REDIS_PORT/0"
export FLASK_DRAMATIQ_BROKER_URL="redis://localhost:$E2E_REDIS_PORT/0"
export FLASK_SERVER_NAME="127.0.0.1:$E2E_PORT"
# Talisman would otherwise force HTTPS, and werkzeug's adhoc TLS drops
# concurrent asset requests (fonts, avatars) often enough to be flaky.
export FLASK_TALISMAN_FORCE_HTTPS=false
export FLASK_MAIL_DEBUG=1
export FLASK_MAIL_SENDER=e2e@example.com
export FLASK_MAIL_SUPPRESS_SEND=1

# Wait for the Procfile's redis process: the app connects to it at import time.
i=0
while [ "$i" -lt 30 ]; do
    redis-cli -p "$E2E_REDIS_PORT" ping >/dev/null 2>&1 && break
    i=$((i + 1))
    sleep 1
done

# A fresh database each run, so tests never inherit state from the last one.
rm -f "$E2E_DIR/e2e.db"
uv run flask initdb
uv run flask createuser --role admin --name Admin "$E2E_EMAIL" "$E2E_PASSWORD"
uv run flask script e2e_playwright/seed.py

exec uv run flask run --port "$E2E_PORT" --host 127.0.0.1
