.PHONY: test full-test clean setup default

SRC=abilian/sbe
PKG=$(SRC)

INSTANCE_FOLDER=$(shell 												\
	$(VIRTUAL_ENV)/bin/python											\
	 -c 'from flask import Flask; print Flask("myapp").instance_path')


all: test lint

install:
	pip install -r requirements.txt

#
# Environment
#
develop: update-env setup-git
	pip uninstall -y abilian-core
	pip install -q -e ../abilian-core

update-env:
	@echo "--> Installing/updating dependencies"
	pip install -U setuptools
	pip install -U -r requirements.txt
	pip install -U -r etc/git-requirements.txt
	pip install -U -r etc/dev-requirements.txt
	pip install -e .
	yarn
	@echo ""

setup-git:
	@echo "--> Configuring git and installing hooks"
	git config branch.autosetuprebase always
	pre-commit install --install-hooks
	@echo ""

#
# testing
#
instance:
ifndef VIRTUAL_ENV
	@echo "********************************************************************"
	@echo "Error: not running in virtualenv."
	@echo "Please activate virtualenv. (\"source /path/to/env_dir/bin/activate\")"
	@echo "********************************************************************"
	@exit 1;
endif
	pip install -r requirements.txt
	pip install -e .
	@mkdir -pv "$(INSTANCE_FOLDER)"
	@cp -v "etc/config_dev.py" "$(INSTANCE_FOLDER)/config.py"
	@cp -v "etc/logging-dev.yml" "$(INSTANCE_FOLDER)/logging.yml"
	@sed -i -e 's#INSTANCE_FOLDER#$(INSTANCE_FOLDER)#' "$(INSTANCE_FOLDER)/config.py"
	@echo "********************************************************************************"
	@echo "Setup complete!"
	@echo "config is here: $(INSTANCE_FOLDER)/config.py"
	@echo "You may edit it before first run, in particular SQLALCHEMY_DATABASE_URI"
	@echo "Default database is sqlite file based: $(INSTANCE_FOLDER)/data.db"
	@echo
	@echo "you may now run:"
	@echo "python manage.py initdb"
	@echo "python manage.py run"
	@echo "********************************************************************************"


#
# testing
#
test:
	pytest --ff -x --tb=short $(PKG) tests

test-with-coverage:
	pytest --tb=short --durations 10 \
		--cov $(PKG) \
		--cov-config etc/coverage.rc \
		--cov-report term-missing $(SRC) tests

test-long:
	RUN_SLOW_TESTS=True pytest -x $(SRC) tests

vagrant-tests:
	vagrant up
	vagrant ssh -c /vagrant/deploy/vagrant_test.sh
	# We could also do this:
	#vagrant ssh -c 'cp -a /vagrant src && cd src && tox'

#
# Linting
#
lint: lint-js lint-py lint-less lint-doc lint-other

lint-js:
	@echo "--> Linting JavaScript files"
	yarn run eslint abilian/sbe/static/js

lint-less:
	@echo "--> Linting Less files"
	yarn run stylelint abilian/sbe/static/less/**/*.less

lint-py:
	@echo "--> Linting Python files"
	@make flake8
	# @make lint-py3k
	@make lint-mypy

flake8:
	flake8 abilian tests

lint-py3k:
	pylint --py3k abilian tests

lint-mypy:
	-mypy abilian

lint-doc:
	@echo "--> Linting .rst files"
	rst-lint *.rst

lint-other:
	@echo "--> Linting .travis.yml"
	travis lint --no-interactive

#
# Formatting
#
format: format-py format-js

format-py:
	black abilian demo tests *.py
	isort -rc abilian demo tests *.py

format-js:
	yarn run prettier --trailing-comma es5 --write \
		./abilian/sbe/static/js/**.js

futurize:
	isort -a  "from __future__ import absolute_import, print_function, unicode_literals"
		-rc abilian demo tests *.py

#
# running
#
run:
	python manage.py runserver

run-uwsgi:
	uwsgi --http 127.0.0.1:8080 --need-app --disable-logging --wsgi-file wsgi.py --processes 1 --threads 4


#
# Everything else
#
boot:
	./manage.py config init
	./manage.py initdb
	./manage.py createadmin admin@example.com admin

clean:
	find . -name "*.pyc" -delete
	find . -name .DS_Store -delete
	find . -name __pycache__ -delete
	find . -type d -empty -delete
	rm -rf .mypy_cache .cache .eggs .pytest_cache
	rm -rf instance/cache instance/tmp instance/webassets instance/whoosh
	rm -f migration.log
	rm -rf build dist
	rm -rf data tests/data tests/integration/data
	rm -rf tmp tests/tmp tests/integration/tmp
	rm -rf cache tests/cache tests/integration/cache
	rm -rf *.egg-info *.egg .coverage
	rm -rf whoosh tests/whoosh tests/integration/whoosh
	rm -rf doc/_build
	rm -rf static/gen static/.webassets-cache
	rm -rf htmlcov ghostdriver.log coverage.xml junit*.xml
	rm -rf tests.functional.test/

tidy: clean delete-cache
	rm -rf instance/data
	rm -rf .tox

# remove template cache
delete-cache:
	@echo "--> Removing template cache"
	rm -rf ./instance/webassets/compiled/*
	rm -rf ./instance/webassets/cache/*


update-pot:
	python setup.py extract_messages update_catalog compile_catalog


release:
	rm -rf /tmp/abilian-sbe
	git clone . /tmp/abilian-sbe
	cd /tmp/abilian-sbe ; python setup.py sdist
	cd /tmp/abilian-sbe ; python setup.py sdist upload

update-deps:
	pip install -U pip pip-tools setuptools wheel
	pip-compile -U > /dev/null
	pip-compile > /dev/null
	git --no-pager diff requirements.txt

sync-deps:
	pip install -U pip pip-tools setuptools wheel
	pip-sync
	# pip install -r requirements.txt
	pip install -r etc/dev-requirements.txt
	pip install -e .
