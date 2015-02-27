# coding=utf-8
"""
"""
from __future__ import absolute_import

import setuptools
from distutils.command.build import build as _build
from setuptools.command.sdist import sdist as _sdist
from setuptools.command.develop import develop as _develop
import setup_util as deps

install_requires = deps.parse_requirements([u'requirements.txt'])
dependency_links = deps.parse_dependency_links([u'requirements.txt'])
dev_requires = deps.parse_requirements([u'dev-requirements.txt'])

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
  url='http://docs.abilian.com/',
  license='LGPL',
  author='Abilian SAS',
  author_email='contact@abilian.com',
  description='Social Business / Enterprise Social Networking platform',
  packages=['abilian.sbe'],
  zip_safe=False,
  platforms='any',
  setup_requires=['setuptools-git', 'setuptools_scm'],
  install_requires=install_requires,
  extras_require={
    'tests': dev_requires,
    'dev': dev_requires,
  },
  dependency_links=dependency_links,
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
