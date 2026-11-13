.PHONY: test test-mariadb test-mariadb-docker unit full-test pep8 clean setup

default: lint-ruff test lint
all: default


#
# testing
#

## Run tests
test:
	# pytest -n auto
	pytest tests

MARIADB_TEST_URI ?= mysql+pymysql://sbe:sbe@127.0.0.1/sbe_test?charset=utf8mb4

## Run tests against MariaDB
test-mariadb:
	SQLALCHEMY_DATABASE_URI="$(MARIADB_TEST_URI)" pytest tests

DOCKER_TESTS = docker compose -f tests/docker/compose.yaml

## Run tests against MariaDB, database and tests both in Docker
test-mariadb-docker:
	$(DOCKER_TESTS) run --rm --build tests; status=$$?; \
	$(DOCKER_TESTS) down; exit $$status

test-with-coverage:
	pytest \
		--cov extranet --cov abilian \
	  	--cov-report term-missing

test-with-validator:
	VALIDATOR_URL=http://html5.validator.nu/ pytest

test-long:
	RUN_SLOW_TESTS=True pytest -x

test-assets:
	@(if flask assets -v --parse-templates build 2>&1 \
	   | grep --silent "Failed, error was: ExternalTool: subprocess returned a non-success result code"; \
	then echo "Failed"; exit 1; \
	else echo "Success"; exit 0; \
	fi)


#
# Linting
#
.PHONY: check
## Statically check code, dependencies, etc.
check: lint

lint-ruff:
	ruff check src tests

.PHONY: lint
lint: lint-ruff

    #.PHONY: lint-py
    #lint-py:
	#flake8 src tests
	# deptry src
	# python -m pyanalyze --config-file pyproject.toml
	# mypy --show-error-codes src tests
	# pyright src tests

.PHONY: lint-mypy
lint-mypy:
	mypy --show-error-codes src tests

.PHONY: lint-pyright
lint-pyright:
	pyright src tests


.PHONY: format
format:
	ruff format src tests *.py
	markdown-toc -i README.md
	markdown-toc -i docs/roadmap.md

#
# Everything else
#
.PHONY: run
## Run dev server
run:
	honcho -f Procfile.dev start

.PHONY:
run-ssl: run-ssl
	gunicorn -w1 --certfile=ssl/server.crt --keyfile=ssl/server.key --timeout 300 \
		--bind "0.0.0.0:5443" --pid run/gunicorn.pid wsgi:app

.PHONY: clean
## Clean up directory
clean:
	find . -name "*.pyc" -print0 | xargs -0 rm -f
	find . -depth -type d -name __pycache__ -exec rm -rf {} \;
	rm -rf build dist tmp __pycache__
	rm -rf pip-wheel-metadata
	rm -rf *.egg-info *.egg .coverage .eggs
	rm -rf doc/_build htmlcov
	rm -rf instance/cache instance/webassets
	rm -rf src/instance/cache src/instance/webassets
	rm -rf .mypy_cache .pytest_cache

.PHONY: tidy
## Make super-clean
tidy: clean
	rm -rf .tox .nox

.PHONY:
update-pot: update-pot
	python setup.py extract_messages update_catalog compile_catalog


.PHONY: install
## Install dependencies
install:
	@echo "--> Installing / updating python dependencies for development"
	@echo "Make sure that you have uv installed"
	uv sync
	@echo "--> Activating pre-commit hook"
	pre-commit install
	@echo "Remember to run `uv run $SHELL` to activate the virtualenv"
	yarn


.PHONY: update-deps
update-deps:  ## Update dependencies
	uv sync -U
	uv export -o requirements.txt
	pre-commit autoupdate
	uv pip list --outdated


.PHONY: help
help:
	adt help-make


.PHONY: publish
## Publish to PyPI
publish: clean
	git push --tags
	uv build
	twine upload dist/*
