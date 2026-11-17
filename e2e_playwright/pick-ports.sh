#!/bin/sh
# Print `export E2E_PORT=... E2E_REDIS_PORT=...` for a caller to eval.
#
# The suite used to hardcode 8899 and 6399. Any other project of yours holding
# one of them made the run die with "Address already in use" -- and the port is
# needed by two sibling processes (`web` serves on it, `tests` fetches from it),
# so it has to be settled once, before honcho starts them, rather than by each.
#
# A port already set in the environment is passed through untouched, so
# `E2E_PORT=8899 make test-e2e` still pins it.
set -e

python3 - "$@" <<'PY'
import os
import random
import socket

WANTED = ("E2E_PORT", "E2E_REDIS_PORT")
PORTS = range(20000, 61000)


def bind_free_port() -> socket.socket:
    while True:
        sock = socket.socket()
        try:
            sock.bind(("127.0.0.1", random.choice(PORTS)))
        except OSError:
            sock.close()
            continue
        return sock


# Held open together, so no two can be handed the same number, and released
# only once all are chosen.
held = []
for name in WANTED:
    if os.environ.get(name):
        print(f"export {name}={os.environ[name]}")
        continue
    sock = bind_free_port()
    held.append(sock)
    print(f"export {name}={sock.getsockname()[1]}")

for sock in held:
    sock.close()
PY
