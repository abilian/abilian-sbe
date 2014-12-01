#!/bin/sh

# Simplistic provisionning script for Ubuntu, called by Vagrant.

apt-get update
apt-get upgrade -y
apt-get install -y python-dev python-virtualenv python-pip git \
  build-essential imagemagick libpq-dev libxslt1-dev npm unoconv \
  libjpeg-dev python-tox virtualenvwrapper poppler-utils

ln -sf /usr/bin/nodejs /usr/local/bin/node

npm install -g less
npm install -g phantomjs

# In case these are outdated.
pip install -U tox pip

