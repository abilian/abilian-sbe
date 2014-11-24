#!./bin/python

import subprocess
import urllib
import time

# Some random number
BIND = '0.0.0.0'
PORT = 4034
HOME = "http://{}:{}/".format(BIND, PORT)

subprocess.call(['./bin/pip', 'install', 'gunicorn'])

p = subprocess.Popen(["./bin/gunicorn",
                      'wsgi:app',
                      '-b', '{}:{}'.format(BIND, PORT)])

try:
  # Just in case
  time.sleep(5)
  page = urllib.urlopen(HOME).read()
  assert "Welcome to Abilian" in page
finally:
  p.terminate()
  p.wait()
