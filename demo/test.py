#!./bin/python

from __future__ import absolute_import, print_function, unicode_literals

import subprocess
import time

from six.moves.urllib.parse import urlopen

# Some random number
BIND = '0.0.0.0'
PORT = 4034
HOME = "http://{}:{}/".format(BIND, PORT)

subprocess.call(['./bin/pip', 'install', 'gunicorn'])

p = subprocess.Popen(
    ["./bin/gunicorn", 'wsgi:app', '-b', '{}:{}'.format(BIND, PORT)],
)

try:
    # Just in case
    time.sleep(5)
    page = urlopen(HOME).read()
    assert "Welcome to Abilian" in page
finally:
    p.terminate()
    p.wait()
