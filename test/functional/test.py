# encoding: utf-8
"""
Test the application using py.test, Selenium and tesliveserver.
"""

import pytest
from selenium import webdriver
import testliveserver as tls


PORT = 5001
ROOT = "http://localhost:{}/".format(PORT)


@pytest.fixture(scope='module')
def app(request):
  app = tls.Flask("run.py", port=PORT)
  app.name = "Flask"

  try:
    # Run the live server.
    app.start(kill=True)
  except Exception as e:
    # Skip test if not started.
    pytest.fail(e.message)

  request.addfinalizer(lambda: app.stop())
  return app


@pytest.fixture(scope='module')
def browser(request):
  tls.port_in_use(PORT, True)

  browser = webdriver.PhantomJS()
  browser.implicitly_wait(3)

  request.addfinalizer(lambda: browser.quit())
  return browser


def test_home(browser, app):
  browser.get(ROOT)
  print "OK"

def test_login(browser, app):
  browser.get(ROOT + 'login')
  browser.find_element_by_name('email').send_keys("admin@example.com")
  browser.find_element_by_name('password').send_keys("admin")
  button = browser.find_element_by_xpath("//form[@name='login']//button")
  button.click()

  assert "Welcome to Abilian" in browser.find_element_by_xpath("/html/body").text

