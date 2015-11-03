#!/bin/bash

# Exit on first error
set -e


if [ ! -f ./bin/python ]
then
  echo "Creating virtualenv"
  virtualenv .
fi
. ./bin/activate

pip install -U setuptools

echo "Installing Abilian SBE and dependencies"
pip install -r ../requirements.txt
pip install -e ..

# create config & instance dirs
if [ ! -f var/sbe-demo-instance/config.py ]
then
  echo "Creating, then tweaking config"
  ./manage.py config init
fi

sed -i -e "s/localhost:6379/localhost:19876/" var/sbe-demo-instance/config.py

# run redis
redis-server ./redis.conf || { echo "Fail to run redis"; exit 1; }
# let redis start and create pid file
sleep 1
REDIS_PID=$(cat "var/sbe-demo-instance/data/redis.pid")
trap "kill ${REDIS_PID}" INT TERM EXIT;

# create db
if [ ! -f var/sbe-demo-instance/data/db.sqlite ]
then
  echo "Creating DB"
  ./manage.py initdb

  echo "Creating admin user with email 'admin@example.com' and password 'admin'"
  ./manage.py createadmin admin@example.com admin
fi

echo "Now type './manage.py run' to launch the server"
