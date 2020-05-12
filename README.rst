About
=====

Abilian SBE (Social Business Engine) is a platform for social business applications, and more specifically collaborative / enterprise 2.0 business applications, such as enterprise social networks (ESN).

Abilian SBE revolves around the concept of *communities*, which are collaborative spaces with services such as lightweight document management, discussions, wikis, user timelines, etc.

It is based on the `Abilian Core <http://abilian-core.readthedocs.org/en/latest/>`_ project which provide the basic services, on top of Flask and SQLAlchemy.

Abilian SBE is used by several major customers in production, since mid 2013.

.. image:: https://static.pepy.tech/badge/abilian-core
   :target: https://pepy.tech/project/abilian-core

Screenshots
-----------

.. image:: https://raw.githubusercontent.com/abilian/abilian-sbe/master/docs/images/screenshot-3.png

.. image:: https://raw.githubusercontent.com/abilian/abilian-sbe/master/docs/images/screenshot-2.png

.. image:: https://raw.githubusercontent.com/abilian/abilian-sbe/master/docs/images/screenshot-1.png


Install
=======

Prerequisites (native dependencies)
-----------------------------------

- Python 2.7, ``virtualenv``, ``pip``
- `Redis <http://redis.io/>`_
- Sqlite, or a postgresql database.
- A few image manipulation libraries (``libpng``, ``libjpeg``...)
- ``poppler-utils``, ``unoconv``, ``LibreOffice``, ``ImageMagick``.
- `{Less} <http://lesscss.org/>`__ css pre-processor
- A Java environment (JRE 1.7 for example). The `closure compiler
  <https://developers.google.com/closure/compiler/>`_ is used for minifying
  javascript files. You don't have to install the compiler yourself, but a Java
  environment is required.

Get a working application
-------------------------

The following commands will create a virtualenv for the application,
install a script named ``abilian_sbe``, launch development server and
open a setupwizard in your browser:

.. code:: bash

    $ virtualenv sbe
    $ cd sbe; source bin/activate
    $ pip install -U setuptools pip
    $ pip install abilian-sbe
    $ python -m abilian.sbe.app setup_sbe_app

MAC OS + Homebrew
-----------------

You will need to install the following packages using homebrew
(**before** running ``pip install ...``):

::

    brew install python2.7 jpeg git libmagic poppler imagemagick

Running with gunicorn
---------------------

.. code:: bash

    gunicorn 'abilian.sbe.app.create_app()'


Developing
==========

Branching policy
----------------

We currently have two branches:

- `master` for stable version (0.3.x)
- `develop` for next version (0.4.devx)

Testing
-------

Short test
~~~~~~~~~~

Make sure all the dependencies are installed (cf. above), then run ``make
test``.

With coverage
~~~~~~~~~~~~~

Run ``make test-with-coverage``.

Full test suite
~~~~~~~~~~~~~~~

Install `tox <http://pypi.python.org/pypi/tox>`_. Run ``tox -e ALL``.

2 environments are available:

- ``py27``: uses in-memory sqlite
- ``py27_postgres``: uses local postgresql server (you need to first create a
   database, and user/password; tox uses environment variables
   ``POSTGRES_HOST``, ``POSTGRES_PORT``, ``POSTGRES_DB``, ``POSTGRES_USER``,
   ``POSTGRES_PASSWORD``)

Build Status
------------

The project is under continuous integration with Travis and CircleCI:

.. image:: https://travis-ci.org/abilian/abilian-sbe.svg?branch=master
   :target: https://travis-ci.org/abilian/abilian-sbe

.. image:: https://coveralls.io/repos/abilian/abilian-sbe/badge.svg?branch=master
   :target: https://coveralls.io/r/abilian/abilian-sbe?branch=master

Links
=====

- `Discussion list (Google Groups) <https://groups.google.com/forum/#!foru      m/abilian-users>`_
- `Documentation <http://docs.abilian.com/>`_
- `GitHub repository <https://github.com/abilian/abilian-sbe>`_
- `Corporate support <http://www.abilian.com>`_
