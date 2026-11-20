#!/bin/sh
# Serve the pre-migration UI, for visual comparison against the current one.
#
# "At least as good as the old one" is only checkable against the old one, so
# this boots a second instance from a worktree of `main`, which still has the
# LESS/flask-assets pipeline and Bootstrap:
#
#     git worktree add ../sbe-baseline main
#     cd ../sbe-baseline && uv sync && npm install
#
# Same seed data, same ports discipline as serve.sh, different everything else:
# port 8898, its own SQLite file, and redis database 1 so the two instances
# cannot see each other's queues.
set -e

: "${BASELINE_ROOT:=$(CDPATH= cd -- "$(dirname -- "$0")/../../sbe-baseline" && pwd)}"
: "${E2E_DIR:=/tmp/abilian-sbe-e2e}"
: "${BASELINE_PORT:=8898}"
: "${E2E_REDIS_PORT:=6399}"
: "${E2E_EMAIL:=admin@example.com}"
: "${E2E_PASSWORD:=e2e-password}"

SEED="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/seed.py"

mkdir -p "$E2E_DIR"
cd "$BASELINE_ROOT"

export FLASK_DEBUG=0
export FLASK_SECRET_KEY=e2e-secret
export FLASK_SQLALCHEMY_DATABASE_URI="sqlite:///$E2E_DIR/baseline.db"
export FLASK_REDIS_URI="redis://localhost:$E2E_REDIS_PORT/1"
export FLASK_DRAMATIQ_BROKER_URL="redis://localhost:$E2E_REDIS_PORT/1"
export FLASK_SERVER_NAME="127.0.0.1:$BASELINE_PORT"
# TALISMAN_FORCE_HTTPS is an addition on the tailwind branch; `main` forces
# HTTPS unconditionally, so serve TLS. (Debug mode would dodge Talisman but
# puts webassets in debug too, which serves raw .less the browser cannot
# parse -- an unstyled baseline is worse than useless.)
export FLASK_PREFERRED_URL_SCHEME=https
export FLASK_MAIL_DEBUG=1
# The old pipeline shells out to lessc on the first page render.
export FLASK_LESS_BIN="$BASELINE_ROOT/node_modules/.bin/lessc"

i=0
while [ "$i" -lt 30 ]; do
    redis-cli -p "$E2E_REDIS_PORT" ping >/dev/null 2>&1 && break
    i=$((i + 1))
    sleep 1
done

rm -f "$E2E_DIR/baseline.db"
uv run flask initdb
uv run flask createuser --role admin --name Admin "$E2E_EMAIL" "$E2E_PASSWORD"
uv run flask script "$SEED"
# Compiles the LESS bundles up front, so the first screenshot is not of a
# half-built stylesheet.
uv run flask assets build

exec uv run flask run --port "$BASELINE_PORT" --host 127.0.0.1 --cert=adhoc
