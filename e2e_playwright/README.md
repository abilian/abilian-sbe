# End-to-end tests

Browser tests for the things the pytest suite structurally cannot see.

A page whose scripts never loaded, whose widgets never initialised, or whose
icon font is missing still returns a perfectly good 200. That is how the
Tailwind branch came to ship with no icons, no DataTables and a dead documents
module while `pytest` stayed green.

## Running

```bash
make test-e2e
# or:
cd e2e_playwright && honcho start
```

`honcho` starts three processes and exits with pytest's status when the suite
finishes, tearing the others down:

| process | what it does |
|---|---|
| `redis` | throwaway instance on a free port, persistence off, so your own redis and its data are untouched |
| `web`   | `serve.sh`: recreates a SQLite database under `$E2E_DIR`, creates an admin user, serves on a free port |
| `tests` | `run_tests.sh`: waits for the server, then runs pytest |

`pytest-playwright` is **not** a project dependency. `uv run --with` layers it
on and `playwright install` fetches the browser; both are cached after the first
run.

Overridable: `E2E_DIR`, `E2E_PORT`, `E2E_REDIS_PORT`, `E2E_EMAIL`,
`E2E_PASSWORD`, `BROWSER`, `BASE_URL`.

`make test-e2e` evals `pick-ports.sh` before starting honcho, so both ports are
free ones chosen at start. They used to be 8899 and 6399, and anything else on
your machine holding one killed the run with "Address already in use" -- each
port is shared by two sibling processes, so neither can pick it for itself.
Setting `E2E_PORT` or `E2E_REDIS_PORT` still pins that one; a bare
`cd e2e_playwright && honcho start` falls back to the old defaults.

## Why it runs with debug off

Debug mode would point `vite_asset` at a Vite dev server that isn't running, so
the suite would test the wrong asset path — the production one is what ships and
what broke. Debug off also turns on Talisman, so the suite exercises the real
CSP and security headers.

`FLASK_TALISMAN_FORCE_HTTPS=false` keeps it on plain HTTP. Under TLS the
werkzeug dev server drops enough concurrent asset requests (fonts, avatars) to
make the suite flaky; the CSP and the other headers still apply.

## What it caught

On its first run, against the production configuration:

- **CSP blocked every inline script.** Talisman's default `default-src 'self'`
  policy, which nothing overrode, blocked the AMD shim, `abilian_init.js` and
  the deferred JS, so no legacy JavaScript ran at all. Pre-existing on `devel`.
- **The AMD shim ignored `define(name, factory)`**, the CommonJS-wrapper form
  `hogan-2.0.0.js` uses. Hogan stayed an empty object, `widgets/file.js` threw
  on `Hogan.compile`, and `widgets/image.js` lost its base class with it.
- **`/admin/dashboard` returned 500**: pandas removed the `"M"` offset alias in
  2.2, and the dashboard still used it.
