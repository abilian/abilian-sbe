# coding=utf-8
"""
"""
from __future__ import absolute_import

import setuptools
from distutils.command.build import build as _build
from setuptools.command.sdist import sdist as _sdist
from setuptools.command.develop import develop as _develop

import pip

session = pip.download.PipSession()

_install_requires = pip.req.parse_requirements(
    'requirements.in', session=session)
install_requires = [str(ir.req) for ir in _install_requires]

_dev_requires = pip.req.parse_requirements(
    'etc/dev-requirements.txt', session=session)
dev_requires = [str(ir.req) for ir in _dev_requires]

LONG_DESCRIPTION = open('README.rst', 'r').read()


class build(_build):
  sub_commands = [('compile_catalog', None)] + _build.sub_commands


class sdist(_sdist):
  sub_commands = [('compile_catalog', None)] + _sdist.sub_commands


class develop(_develop):
  def run(self):
    _develop.run(self)
    self.run_command('compile_catalog')


setuptools.setup(
  name='abilian-sbe',
  use_scm_version=True,
  url='https://github.com/abilian/abilian-sbe',
  license='LGPL',
  author='Abilian SAS',
  author_email='contact@abilian.com',
  description='Social Business platform, including: document management, wiki, forum, enterprise social networking, and more',
  long_description=LONG_DESCRIPTION,
  packages=['abilian.sbe'],
  zip_safe=False,
  platforms='any',
  setup_requires=['babel', 'setuptools-git', 'setuptools_scm>=1.5.5'],
  install_requires=install_requires,
  extras_require={
    'tests': dev_requires,
    'dev': dev_requires,
  },
  # dependency_links=dependency_links,
  include_package_data=True,
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Environment :: Web Environment',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Framework :: Flask',
  ],
  cmdclass={
    'build': build,
    'sdist': sdist,
    'develop': develop,
  },
)
