# encoding: utf-8
"""
Test the application using py.test and splinter.

See: https://splinter.readthedocs.org/

Also, we're using pytest-splinter
(https://github.com/pytest-dev/pytest-splinter) to inject the browser as
a pytest fixture.
"""
import tempfile
import shutil
import multiprocessing
from pathlib import Path
import pytest
import pytest_splinter.plugin  # noqa

from abilian.sbe.app import Application


# TODO: switch to another port if this one is not available?
PORT = 5000
ROOT = "http://localhost:{}".format(PORT)


# We're using phantomjs as our default browser.
@pytest.fixture(scope='session')  # pragma: no cover
def splinter_webdriver(request):
  return 'phantomjs'

@pytest.fixture(scope='module')
def instance_path(request):
  """
  creates a temporary directory for instance data
  """
  tmp_dir = tempfile.mkdtemp(prefix='tmp-pytest-', suffix='-abilian-sbe')

  def clear():
    shutil.rmtree(tmp_dir)

  request.addfinalizer(clear)

@pytest.fixture(scope='module')
def app(request, instance_path):
  app = Application(instance_path=instance_path)

  # FIXME: need a working environment (DB, Redis...)
  # with app.app_context():
  #   app.create_db()

  def worker(app, port):
    app.run(port=port)

  process = multiprocessing.Process(target=worker, args=(app, PORT))

  try:
    process.start()
  except Exception as e:
    pytest.fail(e.message)

  def finalizer():
    if process:
      process.terminate()

  request.addfinalizer(finalizer)

  return app


def test_home(browser, app):
  browser.visit(ROOT)


def test_login(browser, app):
  browser.visit(ROOT + '/user/login')
  browser.fill('email', "admin@example.com")
  browser.fill('password', "admin")
  button = browser.find_by_xpath("//form[@name='login']//button")
  assert button

  # FIXME: at this point this raises an error because we have to set up the db.
  # button.click()
  # assert "Welcome to Abilian" in browser.find_element_by_xpath("/html/body").text


def test_forgotten_pw(browser, app):
  browser.visit(ROOT + '/user/forgotten_pw')
