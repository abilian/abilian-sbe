# Docker-based tests

Runs the test suite against MariaDB, with both the database and the tests in containers. Nothing to install but Docker.

```bash
make test-mariadb-docker
```

The code is copied into the image (not bind-mounted), so it also works with a remote Docker context.

To run a subset of the tests:

```bash
docker compose -f tests/docker/compose.yaml run --rm --build tests pytest tests/b_integration
docker compose -f tests/docker/compose.yaml down
```

Not covered: tests that need Redis or LibreOffice are skipped.
