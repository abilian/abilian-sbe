# coding=utf-8
"""
"""
from __future__ import absolute_import, print_function, unicode_literals

from distutils.command.build import build as _build

import setuptools
from setuptools.command.develop import develop as _develop
from setuptools.command.sdist import sdist as _sdist

LONG_DESCRIPTION = open("README.rst", "r").read()


class build(_build):
    sub_commands = [("compile_catalog", None)] + _build.sub_commands


class sdist(_sdist):
    sub_commands = [("compile_catalog", None)] + _sdist.sub_commands


class develop(_develop):
    def run(self):
        _develop.run(self)
        self.run_command("compile_catalog")


setuptools.setup(
    name="abilian-sbe",
    url="https://github.com/abilian/abilian-sbe",
    license="LGPL",
    author="Abilian SAS",
    author_email="contact@abilian.com",
    description="Social Business platform, including: document management, wiki, "
    "forum, enterprise social networking, and more",
    long_description=LONG_DESCRIPTION,
    packages=["abilian.sbe"],
    zip_safe=False,
    platforms="any",
    setup_requires=["babel"],
    include_package_data=True,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Framework :: Flask",
    ],
    cmdclass={"build": build, "sdist": sdist, "develop": develop},
)
