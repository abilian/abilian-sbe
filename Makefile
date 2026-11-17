.PHONY: test test-mariadb test-mariadb-docker test-postgres-docker unit full-test pep8 clean setup

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

# CI adds `-f tests/docker/compose.host-network.yaml` through DOCKER_TESTS_EXTRA.
DOCKER_TESTS = docker compose -f tests/docker/compose.yaml $(DOCKER_TESTS_EXTRA)

## Run tests against MariaDB or PostgreSQL, database and tests both in Docker
test-mariadb-docker test-postgres-docker: test-%-docker:
	$(DOCKER_TESTS) run --rm --build tests-$*; status=$$?; \
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
lint:
	@make lint-ruff
	# @make typecheck
	@make lint-py
	@make lint-imports

.PHONY: lint-imports
lint-imports:
	## Check the architectural boundaries (contracts in pyproject.toml)
	lint-imports

.PHONY: lint-py
lint-py:
	deptry src

.PHONY: typecheck
typecheck:
	pyrefly check src
	ty check src

.PHONY: format
format:
	ruff format src tests *.py
	ruff check --fix src tests
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
	rm -rf .tox .nox .venv

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
	npm install
	$(MAKE) front


.PHONY: test-e2e
test-e2e:  ## Run the Playwright browser tests
	cd e2e_playwright && eval "$$(sh pick-ports.sh)" && honcho start

.PHONY: front
front:  ## Build the front-end assets (CSS/JS) into the package
	cd vite && npm install && npm run build

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
	$(MAKE) front
	uv build
	twine upload dist/*
