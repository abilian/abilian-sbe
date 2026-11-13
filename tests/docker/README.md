# Docker-based tests

Runs the test suite against MariaDB or PostgreSQL, with both the database and the tests in containers. Nothing to install but Docker.

```bash
make test-mariadb-docker
make test-postgres-docker
```

The code is copied into the image (not bind-mounted), so it also works with a remote Docker context.

To run a subset of the tests (use `tests-postgres` for PostgreSQL):

```bash
docker compose -f tests/docker/compose.yaml run --rm --build tests-mariadb pytest tests/b_integration
docker compose -f tests/docker/compose.yaml down
```

Not covered: tests that need Redis or LibreOffice are skipped.
