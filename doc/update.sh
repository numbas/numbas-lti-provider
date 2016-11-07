#!/bin/bash
source /opt/numbas_lti_python/bin/activate
cd /srv/numbas-lti-provider
git pull origin master
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart numbas_lti:
