#!/usr/bin/bash

# set up user group
sudo addgroup numbas_lti
sudo adduser ubuntu numbas_lti
sudo adduser www-data numbas_lti
sudo adduser ubuntu www-data

# install packages
sudo apt-get install apache2 redis-server postgresql postgresql-server-dev-9.5 libxml2-dev libxslt1-dev python-dev lib32z1-dev python3-pip supervisor git
sudo pip3 install virtualenv

# get the numbas-lti-provider code
sudo git clone https://github.com/numbas/numbas-lti-provider.git /srv/numbas-lti-provider
sudo chown -R root:numbas_lti /srv/numbas-lti-provider

# create media and static file directories
sudo mkdir /srv/numbas-lti-media
sudo mkdir /srv/numbas-lti-static
sudo chown -R root:numbas_lti /srv/numbas-lti-media
sudo chown -R www-data:www-data /srv/numbas-lti-static
sudo chmod -R 770 /srv/numbas-lti-*

# create the virtualenv for the python modules
sudo virtualenv /opt/numbas_lti_python
sudo chown -R root:numbas_lti /opt/numbas_lti_python
sudo chmod -R 770 /opt/numbas_lti_python
source /opt/numbas_lti_python/bin/activate

# install python modules
cd /srv/numbas-lti-provider
pip install -r requirements.txt
pip install asgi_redis psycopg2

sudo -u postgres psql -c "CREATE USER numbas_lti;"
createdb -U numbas_lti numbas_lti
