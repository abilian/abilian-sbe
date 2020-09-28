# -*- coding: utf-8 -*-

# DO NOT EDIT THIS FILE!
# This file has been autogenerated by dephell <3
# https://github.com/dephell/dephell

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


import os.path

readme = ""
here = os.path.abspath(os.path.dirname(__file__))
readme_path = os.path.join(here, "README.rst")
if os.path.exists(readme_path):
    with open(readme_path, "rb") as stream:
        readme = stream.read().decode("utf8")


setup(
    long_description=readme,
    name="abilian-sbe",
    version="0.5.9",
    description="Social Business platform, including: document management, wiki, forum, enterprise social networking, and more",
    python_requires="==3.*,>=3.6.0",
    project_urls={"repository": "https://github.com/abilian/abilian-sbe"},
    author="Abilian SAS",
    license="LGPL-2.0-or-later",
    packages=[
        "abilian",
        "abilian.sbe",
        "abilian.sbe.apps",
        "abilian.sbe.apps.calendar",
        "abilian.sbe.apps.calendar.tests",
        "abilian.sbe.apps.communities",
        "abilian.sbe.apps.communities.tests",
        "abilian.sbe.apps.communities.views",
        "abilian.sbe.apps.documents",
        "abilian.sbe.apps.documents.cmis",
        "abilian.sbe.apps.documents.tests",
        "abilian.sbe.apps.documents.views",
        "abilian.sbe.apps.documents.webdav",
        "abilian.sbe.apps.forum",
        "abilian.sbe.apps.forum.tests",
        "abilian.sbe.apps.main",
        "abilian.sbe.apps.notifications",
        "abilian.sbe.apps.notifications.tasks",
        "abilian.sbe.apps.notifications.views",
        "abilian.sbe.apps.preferences",
        "abilian.sbe.apps.preferences.panels",
        "abilian.sbe.apps.social",
        "abilian.sbe.apps.social.tests",
        "abilian.sbe.apps.social.views",
        "abilian.sbe.apps.wall",
        "abilian.sbe.apps.wiki",
        "abilian.sbe.apps.wiki.tests",
    ],
    package_dir={"": "."},
    package_data={
        "abilian.sbe": [
            "static/csv/*.csv",
            "static/fileicons/*.png",
            "static/fileicons/*.txt",
            "static/icons/*.png",
            "static/images/*.jpg",
            "static/images/*.png",
            "static/img/*.jpg",
            "static/img/*.png",
            "static/js/*.js",
            "static/less/*.less",
            "static/less/*.txt",
            "static/less/modules/*.less",
            "static/moment/*.js",
            "static/pdfjs/*.css",
            "static/pdfjs/*.js",
            "static/pdfjs/*.txt",
            "static/pdfjs/cmaps/*.bcmap",
            "static/pdfjs/images/*.cur",
            "static/pdfjs/images/*.gif",
            "static/pdfjs/images/*.png",
            "static/pdfjs/images/*.svg",
            "static/pdfjs/locale/*.properties",
            "static/pdfjs/locale/en-US/*.properties",
            "static/pdfjs/locale/fr/*.properties",
            "static/vendor/*.js",
            "templates/*.html",
            "translations/*.pot",
            "translations/es/LC_MESSAGES/*.mo",
            "translations/es/LC_MESSAGES/*.po",
            "translations/fr/LC_MESSAGES/*.mo",
            "translations/fr/LC_MESSAGES/*.po",
            "translations/tr/LC_MESSAGES/*.mo",
            "translations/tr/LC_MESSAGES/*.po",
            "translations/zh/LC_MESSAGES/*.mo",
            "translations/zh/LC_MESSAGES/*.po",
        ],
        "abilian.sbe.apps.calendar": ["templates/calendar/*.html"],
        "abilian.sbe.apps.communities": ["templates/community/*.html"],
        "abilian.sbe.apps.communities.views": ["data/*.png"],
        "abilian.sbe.apps.documents": [
            "templates/cmis/*.xml",
            "templates/documents/*.html",
            "templates/documents/*.txt",
        ],
        "abilian.sbe.apps.documents.tests": [
            "data/*.xml",
            "data/dummy_files/*.bin",
            "data/dummy_files/*.jpg",
            "data/dummy_files/*.pdf",
            "data/dummy_files/*.txt",
            "data/dummy_files/*.zip",
        ],
        "abilian.sbe.apps.forum": [
            "templates/forum/*.html",
            "templates/forum/mail/*.html",
            "templates/forum/mail/*.txt",
        ],
        "abilian.sbe.apps.forum.tests": ["data/*.email"],
        "abilian.sbe.apps.notifications": [
            "templates/notifications/*.css",
            "templates/notifications/*.html",
            "templates/notifications/*.txt",
        ],
        "abilian.sbe.apps.preferences": ["templates/preferences/*.html"],
        "abilian.sbe.apps.social": [
            "templates/social/*.html",
            "templates/social/mail/*.txt",
        ],
        "abilian.sbe.apps.wall": ["templates/wall/*.html"],
        "abilian.sbe.apps.wiki": ["data/*.txt", "templates/wiki/*.html"],
    },
    install_requires=[
        "abilian-core>=0.11",
        "chardet",
        "flask-babel<2",
        "langid>=1.1",
        "markdown==3.*,>=3.0.0",
        "openpyxl==2.*,>=2.3.0",
        "toolz",
        "validate-email",
        "werkzeug<1",
        "wtforms<2.2",
        "xlwt",
    ],
    extras_require={
        "dev": [
            "black",
            "coverage>=4.1",
            "devtools==0.*,>=0.5.1",
            "docutils==0.15",
            "flake8",
            "flake8-bugbear",
            "flake8-comprehensions",
            "flake8-mutable",
            "flake8-pytest",
            "flake8-super-call",
            "flake8-tidy-imports",
            "flask-debugtoolbar",
            "flask-linktester",
            "gitchangelog==3.*,>=3.0.0",
            "honcho",
            "isort",
            "mastool",
            "mccabe",
            "mypy",
            "pre-commit",
            "pyannotate==1.*,>=1.0.0",
            "pytest",
            "pytest-cov",
            "pytest-flask==1.*,>=1.0.0",
            "pytest-xdist",
            "restructuredtext-lint",
            "sphinx",
            "sphinx-rtd-theme",
            "typeguard",
        ]
    },
)
