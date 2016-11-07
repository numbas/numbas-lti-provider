#!/usr/bin/bash
source /opt/numbas_lti_python/bin/activate
cd /srv/numbas-lti-provider
python manage.py migrate
python manage.py collectstatic --noinput
sudo chown -R www-data:www-data /srv/numbas-lti-static/
sudo service supervisor start
sudo service apache
