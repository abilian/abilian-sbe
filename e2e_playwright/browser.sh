#!/bin/sh
# Serve a Linux Chromium for the screenshot tests, from Playwright's own image.
#
# Screenshots are compared pixel for pixel, and fonts, antialiasing and
# scrollbars differ between macOS and Linux, and between architectures. So the
# browser always runs here: linux/amd64, with the image tag and the Python
# client both pinned by `playwright-version`. It runs on the current Docker
# context; pick it with `docker context use` or DOCKER_CONTEXT.
#
# The browser must load the e2e server as 127.0.0.1:$E2E_PORT, the address
# FLASK_SERVER_NAME expects. With host networking the container shares its
# Docker host's loopback, so on a local Docker host that is the end of it. When
# the context is a remote host over SSH, one SSH connection bridges the two
# loopbacks: -L brings the browser's port here, -R takes the e2e server's port
# there. Started by Procfile.screenshots.
set -e

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VERSION="$(cat "$HERE/playwright-version")"
: "${E2E_PORT:=8899}"
: "${E2E_BROWSER_PORT:=3123}"

# Named, so stopping this script stops the container too: on a remote host,
# killing the local `docker run` client would leave it running there.
NAME="sbe-e2e-browser-$E2E_BROWSER_PORT"
SSH_HOST=""
SOCKET="${TMPDIR:-/tmp}/$NAME.ssh"
cleanup() {
    docker stop -t 2 "$NAME" >/dev/null 2>&1 || true
    if [ -n "$SSH_HOST" ]; then
        ssh -S "$SOCKET" -O exit "$SSH_HOST" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 143' INT TERM

ENDPOINT="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
case "$ENDPOINT" in
ssh://*)
    SSH_HOST="${ENDPOINT#ssh://}"
    # -f returns only once both forwards are up, so the browser can never be
    # asked for a page before the way back to the server exists.
    ssh -f -N -M -S "$SOCKET" -o ExitOnForwardFailure=yes -o BatchMode=yes \
        -L "127.0.0.1:$E2E_BROWSER_PORT:127.0.0.1:$E2E_BROWSER_PORT" \
        -R "127.0.0.1:$E2E_PORT:127.0.0.1:$E2E_PORT" \
        "$SSH_HOST"
    ;;
esac

# In the background with `wait`, so a TERM reaches the trap straight away
# instead of after the container exits.
docker run --rm --init --name "$NAME" --platform linux/amd64 --network host \
    "mcr.microsoft.com/playwright:v$VERSION-noble" \
    npx -y "playwright@$VERSION" run-server --host 127.0.0.1 --port "$E2E_BROWSER_PORT" &
wait $!
