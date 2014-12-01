#!/bin/bash

# exit on error
set -e

virtualenv env
. env/bin/activate

cd /vagrant
pip install -r dev-requirements.txt
pip install -e .
py.test .
