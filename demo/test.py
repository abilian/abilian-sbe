#!./bin/python


import subprocess
import time
# Some random number
from urllib.request import urlopen

BIND = "0.0.0.0"
PORT = 4034
HOME = f"http://{BIND}:{PORT}/"

subprocess.call(["./bin/pip", "install", "gunicorn"])

p = subprocess.Popen(["./bin/gunicorn", "wsgi:app", "-b", f"{BIND}:{PORT}"])

try:
    # Just in case
    time.sleep(5)
    page = urlopen(HOME).read()
    assert "Welcome to Abilian" in page
finally:
    p.terminate()
    p.wait()
