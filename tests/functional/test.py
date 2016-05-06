# encoding: utf-8
"""
Test the application using py.test and splinter.

See: https://splinter.readthedocs.org/

Also, we're using pytest-splinter
(https://github.com/pytest-dev/pytest-splinter) to inject the browser as
a pytest fixture.
"""
import socket
import tempfile
import shutil
import multiprocessing

import pytest
from werkzeug.serving import select_ip_version

from abilian.sbe.app import Application


@pytest.fixture(scope='session')
def app_port(request):
    port = 30000
    hostname = '127.0.0.1'

    address_family = select_ip_version(hostname, port)
    test_socket = socket.socket(address_family, socket.SOCK_STREAM)
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    while port < 60000:
        try:
            test_socket.bind((hostname, port))
            test_socket.close()

        except socket.error as exc:
            if exc.errno != 98:
                # errno(98, Address already in use)
                raise
            port += 1

        break

    return port


@pytest.fixture(scope='session')
def app_root(app_port):
    return "http://localhost:{}".format(app_port)


# We're using phantomjs as our default browser.
@pytest.fixture(scope='session')  # pragma: no cover
def splinter_webdriver(request):
    return 'phantomjs'


@pytest.fixture(scope='session')
def splinter_driver_kwargs():
    """Webdriver kwargs."""
    # set resourceTimeout in the hope it will help jenkins kill phantomjs after
    # tests
    return dict(desired_capabilities={
        'phantomjs.page.settings.resourceTimeout': '30000',  # 30s
    },)


@pytest.fixture(scope='module')
def instance_path(request):
    """Creates a temporary directory for instance data.
    """
    tmp_dir = tempfile.mkdtemp(prefix='tmp-pytest-', suffix='-abilian-sbe')

    def clear():
        shutil.rmtree(tmp_dir)

    request.addfinalizer(clear)
    return tmp_dir


@pytest.fixture(scope='module')
def app(request, instance_path, app_port):
    app = Application(instance_path=instance_path)

    # FIXME: need a working environment (DB, Redis...)
    # with app.app_context():
    #   app.create_db()

    def worker(app, port):
        app.run(port=port)

    process = multiprocessing.Process(target=worker, args=(app, app_port))

    try:
        process.start()
    except Exception as e:
        pytest.fail(e.message)

    def finalizer():
        if process:
            process.terminate()

    request.addfinalizer(finalizer)

    return app


"""
@skip
def test_home(browser, app, app_root):
    browser.visit(app_root)


@skip
def test_login(browser, app, app_root):
    browser.visit(app_root + '/user/login')
    browser.fill('email', "admin@example.com")
    browser.fill('password', "admin")
    button = browser.find_by_xpath("//form[@name='login']//button")
    assert button

    # FIXME: at this point this raises an error because we have to set up the db.
    # button.click()
    # assert "Welcome to Abilian" in browser.find_element_by_xpath("/html/body").text


@skip
def test_forgotten_pw(browser, app, app_root):
    browser.visit(app_root + '/user/forgotten_pw')
"""
