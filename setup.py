# -*- coding: utf-8 -*-

import os
import setuptools

import setup_util as deps

deps_txt = os.path.join('etc', 'deps.txt')
requires = deps.parse_requirements([deps_txt])
depend_links = deps.parse_dependency_links([deps_txt])

setuptools.setup(
  name='abilian.sbe',
  version='0.1dev',
  url='http://www.abilian.com/',
  license='LGPL',
  author='Abilian SAS',
  author_email='contact@abilian.com',
  description='Social Business / Enterprise Social Networking platform',
  long_description=__doc__,
  packages=['abilian.sbe'],
  zip_safe=False,
  platforms='any',
  setup_requires=['setuptools-git'],
  install_requires=requires,
  dependency_links=depend_links,
  include_package_data=True,
  #entry_points = {
  #  'console_scripts': [
  #    'abilian = extranet_spr.commands.manage:main',
  #    'abilian_celery = extranet_spr.commands.celeryctl:main',
  #    ]
  #},
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Environment :: Web Environment',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: BSD License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    ],
)
