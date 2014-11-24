About
=====

TODO.




Install
=======

Prerequisites (native dependencies)
-----------------------------------

- Python 2.7
- A few image manipulation libraries (`libpng`, `libjpeg`...)
- `poppler-utils`, `unoconv`, `LibreOffice`, `ImageMagick`.
- `pip`

Look at the `fabfile.py` for the exact list.

Python modules
--------------

Create a virtualenv (ex: `mkvirtualenv yaka`, assuming you have mkvirtualenv installed).

Then run `pip install -r deps.txt` or `python setup.py develop`.


MAC OS + Homebrew
-----------------

You will need to install the following packages using homebrew (**before** running `pip install ...`):

    brew install python2.7 jpeg git libmagic poppler imagemagick


Testing
=======

Short test
----------

Make sure all the dependencies are installed (cf. above), then
run `make test`.

With coverage
-------------

Run `make test-with-coverage`.

Full test suite
---------------

Install [tox](http://pypi.python.org/pypi/tox). Run `tox -e ALL`.

2 environments are available:

- `py27`: uses in-memory sqlite

- `py27_postgres`: uses local postgresql server (you need to first create
  a database: `extranet_spr_test` with user/password: `extranet_spr_test` /
  `test_pw`)

On a VM
-------

1. Install [vagrant](http://vagrantup.com/) and Fabric (`pip install fabric`).

2. Download a box:

        vagrant box add precise64 http://files.vagrantup.com/precise64.box

3. Use `fabric` and `vagrant` to run tests:

        vagrant up
        fab vagrant upgrade setup
        fab vagrant push stage deploy


Deploy
======

Assuming you deploying to an Ubuntu Precise Pangolin (12.04 LTS) server:

1. Edit the `fabfile.py` and set the address of your server.

2. Run `fab upgrade setup deploy` from you development machine.

3. On the server, verify settings in `config.ini`, then start the server
   manually (run `. env/bin/activate` then `make run`).  (This will be automated
   later.)

Running with gunicorn
---------------------

gunicorn 'extranet_spr:gunicorn_app(config_file="/path/to/config/file.ini")'

Build Status
============

The project is under continuous integration with Travis:

[![Build Status](https://secure.travis-ci.org/sfermigier/yaka.png?branch=master)](https://secure.travis-ci.org/#!/sfermigier/yaka)
