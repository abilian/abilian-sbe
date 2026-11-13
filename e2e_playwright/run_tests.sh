#!/bin/sh
# Wait for the Procfile `web` process to answer, then run the Playwright suite.
# pytest-playwright is not a project dependency -- `uv run --with` layers it on,
# and `playwright install` fetches the browser (both cached after the first run).
set -e

# `make test-e2e` picks a free port and exports it (see pick-ports.sh); this
# default is only for a bare `honcho start`.
: "${E2E_PORT:=8899}"
BASE_URL="${BASE_URL:-http://127.0.0.1:$E2E_PORT}"
BROWSER="${BROWSER:-chromium}"

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

echo "Waiting for $BASE_URL ..."
i=0
while [ "$i" -lt 90 ]; do
    if curl -fsS "$BASE_URL/" >/dev/null 2>&1; then
        echo "Server is up."
        break
    fi
    i=$((i + 1))
    sleep 1
done

if ! curl -fsS "$BASE_URL/" >/dev/null 2>&1; then
    echo "No server at $BASE_URL after 90s -- see the web process above." >&2
    exit 1
fi

# Pinned, because the screenshot tests' browser container must run the same
# version as this client (see browser.sh).
WITH="--with pytest-playwright --with playwright==$(cat e2e_playwright/playwright-version)"

if [ -n "$PW_WS_ENDPOINT" ]; then
    # The first run pulls the image and fetches Playwright, hence the long wait.
    BROWSER_URL="$(echo "$PW_WS_ENDPOINT" | sed 's|^ws:|http:|')"
    echo "Waiting for the browser at $PW_WS_ENDPOINT ..."
    i=0
    until curl -s -o /dev/null "$BROWSER_URL"; do
        i=$((i + 1))
        if [ "$i" -ge 300 ]; then
            echo "No browser at $PW_WS_ENDPOINT after 300s -- see the browser process above." >&2
            exit 1
        fi
        sleep 1
    done
else
    uv run $WITH playwright install "$BROWSER" >/dev/null 2>&1 || true
fi

exec uv run $WITH pytest "${E2E_TESTS:-e2e_playwright}" \
    -v --browser "$BROWSER" --base-url "$BASE_URL"
