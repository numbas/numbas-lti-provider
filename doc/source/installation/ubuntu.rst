.. _installation_ubuntu:

Installation on Ubuntu
######################

You will need:

* Administrator access to a server with at least 4GB of RAM, connected to the internet. 
  A virtual machine is fine.
* A domain name pointed at the server you're going to use. 
  A subdomain (e.g. ``numbas-lti.youruniversity.edu``) is fine.
* An SSL certificate: LTI content must be served over HTTPS. 
  These can be obtained easily and for free from `Let's Encrypt <https://letsencrypt.org/>`_.

These instructions will take a fresh machine running Ubuntu 16.04 or newer and set up the Numbas LTI tool provider to run through NGINX or Apache.
On different operating systems or with different web servers, the process will be different. 
There are alternate instructions for :ref:`installation on RedHat Enterprise Linux 7 <installation-rhel-7>`.

The Numbas LTI provider is a `Django <https://www.djangoproject.com/>`_ app.
See `the Django documentation <https://docs.djangoproject.com/en/2.2/ref/settings/>`_ for configuration options not described here.

We will set up:

* The Numbas LTI provider Django app running inside a virtual Python environment, isolated from the system's Python environment.
* A PostgreSQL database for the LTI provider to use. You can use any database supported by Django; see the `list of supported databases in the Django documentation <https://docs.djangoproject.com/en/2.2/ref/databases/>`_.
* `Supervisord <http://supervisord.org/>`_ will ensure the app is always running.
* The `NGINX webserver <https://nginx.org/>`_ as a reverse proxy to serve the LTI provider to the outside world. 
  If necessary, you can use Apache as a reverse proxy (see the `guide in the Apache documentation <https://httpd.apache.org/docs/2.4/howto/reverse_proxy.html>`_), but it can not handle as many simultaneous connections.

Set up the environment
----------------------

First, install packages, set up users, and create the required paths (you can save this script as a file and run it as root - it doesn't need any user input)::

    #!/usr/bin/bash

    # set up user group
    adduser --disabled-password numbas_lti
    adduser www-data numbas_lti

    # install packages
    apt update
    apt install \
        git redis-server postgresql postgresql-server-dev-all \
        libxml2-dev libxslt1-dev python-dev lib32z1-dev python3-pip supervisor
    pip3 install virtualenv

    # get the numbas-lti-provider code
    git clone https://github.com/numbas/numbas-lti-provider.git /srv/numbas-lti-provider
    cd /srv/numbas-lti-provider
    git checkout v3_STABLE
    chown -R numbas_lti:numbas_lti /srv/numbas-lti-provider

    # create media and static file directories
    mkdir /srv/numbas-lti-media
    mkdir /srv/numbas-lti-static
    chown -R numbas_lti:numbas_lti /srv/numbas-lti-media
    chown -R www-data:www-data /srv/numbas-lti-static
    chmod -R 770 /srv/numbas-lti-*

    # create the virtualenv for the python modules
    virtualenv -p python3 /opt/numbas_lti_python
    chown -R numbas_lti:numbas_lti /opt/numbas_lti_python
    chmod -R 770 /opt/numbas_lti_python

    # install python modules
    cd /srv/numbas-lti-provider
    source /opt/numbas_lti_python/bin/activate
    pip install -r requirements.txt
    pip install channels_redis==3.3.0 psycopg2==2.8.6 redis==3.5.3

Next, create a database and set a password to access it (replace ``$password`` with your chosen password in the following script)::

    sudo -u postgres psql -c "CREATE USER numbas_lti WITH ENCRYPTED PASSWORD '$password' CREATEDB;"
    sudo -u postgres createdb -U numbas_lti numbas_lti -h localhost

Configuring the Numbas LTI provider
-----------------------------------

Run::

    cd /srv/numbas-lti-provider
    source /opt/numbas_lti_python/bin/activate
    python first_setup.py

This script will ask a few questions, and configure the Numbas LTI provider accordingly.
It will set up the database, and create an admin user account which you will use to manage the LTI provider through its web interface.

.. note::

   The first question that the setup script asks is "Is this installation for development?".
   The settings for development mode are not compatible with serving the LTI provider to external clients.

   Only answer 'yes' to this question if the installation is for the purpose of making changes to the LTI provider's code.
   For all other purposes, answer 'no'.

Once you've run this script, the last remaining steps are to start the app, and then set up a webserver to expose it to the outside world.

.. _ubuntu-configure-supervisord:

Configure supervisord
---------------------

`Supervisord <http://supervisord.org/>`_ ensures that the Numbas LTI provider app is always running.

Save the following as :file:`/etc/supervisor/conf.d/numbas_lti.conf`::

    [program:numbas_lti_daphne]
    command=/opt/numbas_lti_python/bin/daphne numbasltiprovider.asgi:application --port 87%(process_num)02d --bind 0.0.0.0 -v 2
    directory=/srv/numbas-lti-provider/
    user=www-data
    autostart=true
    autorestart=true
    stopasgroup=true
    environment=DJANGO_SETTINGS_MODULE=numbasltiprovider.settings
    numprocs=4
    process_name=%(program_name)s_%(process_num)02d
    stderr_logfile=/var/log/supervisor/numbas_lti_daphne_stderr.log
    stdout_logfile=/var/log/supervisor/numbas_lti_daphne_stdout.log

    [program:numbas_lti_huey]
    command=/opt/numbas_lti_python/bin/python /srv/numbas-lti-provider/manage.py run_huey -w 8
    directory=/srv/numbas-lti-provider/
    user=www-data
    autostart=true
    autorestart=true
    redirect_stderr=True
    stopasgroup=true
    environment=DJANGO_SETTINGS_MODULE="numbasltiprovider.settings"
    numprocs=1
    process_name=%(program_name)s_%(process_num)02d
    stderr_logfile=/var/log/supervisor/numbas_lti_huey_stderr.log
    stdout_logfile=/var/log/supervisor/numbas_lti_huey_stdout.log

    [group:numbas_lti]
    programs=numbas_lti_daphne,numbas_lti_huey
    priority=999

.. note::

    If your server must use a proxy to make HTTP or HTTPS requests, you should set environment variables ``HTTP_PROXY`` and ``HTTPS_PROXY`` in the supervisor configuration.
    Add them to the lines starting ``environment=``, for example::

        environment=DJANGO_SETTINGS_MODULE="numbasltiprovider.settings",HTTP_PROXY=http://web.proxy:4321,HTTPS_PROXY=http://web.proxy:4321

Once you've set this up, run::

    systemctl restart supervisor

Supervisord will start the Numbas LTI provider, and restart it automatically if it ever crashes.

Set up a webserver
------------------

We have instructions for two webservers: :ref:`NGINX <install_NGINX>` and :ref:`Apache <install_apache>`.

.. _install_nginx:

With NGINX
**********

`NGINX <https://www.NGINX.com/>`_ is a high performance webserver, ideal for use as a reverse proxy.
It is the recommended option for the Numbas LTI provider.

Install NGINX::

    apt install nginx

Overwrite :file:`/etc/nginx/sites-available/default` with the following::

    upstream backend_hosts {
     server 0.0.0.0:8700;
     server 0.0.0.0:8701;
     server 0.0.0.0:8702;
     server 0.0.0.0:8703;
    }

    server {
        listen 443;
        client_max_body_size 20M;

        ssl on;
        ssl_certificate /etc/ssl/numbas-lti.pem;
        ssl_certificate_key /etc/ssl/numbas-lti.key;

        error_page 502 /502.html;
        location = /502.html {
          root /srv/www/server-error;
        }

        location /static {
            alias /srv/numbas-lti-static;
        }

        location /media {
            alias /srv/numbas-lti-media;
        }

        location / {
            proxy_pass http://backend_hosts;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
            proxy_redirect     off;
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Host $server_name;
            proxy_set_header   X-Scheme https;
            proxy_set_header   X-Forwarded-Proto https;
            proxy_read_timeout 600s;
        }

    }
    
Set the ``ssl_certificate`` and ``ssl_certificate_key`` lines to the paths to your SSL certificate and key files.
If you're using :command:`certbot`, it will add those lines for you.

You should put something in :file:`/srv/www/server-error/502.html`, to be shown when there's a server error.
This can happen if the Numbas LTI provider isn't running, or otherwise fails to communicate with NGINX.

.. _install_apache:
 
With Apache
***********

`Apache <https://httpd.apache.org/>`_ is a very commonly-used webserver.

.. warning::

    While it can be used as a reverse proxy for the Numbas LTI provider, it's not great at dealing with the many simultaneous connections that the LTI provider requires.
    Apache will start having trouble at around 100 simultaneous connections.
    In some circumstances, Apache might be your only option, so the instructions are provided as a reference.

Install required packages::

    apt install apache2
    a2enmod ssl proxy proxy_wstunnel proxy_http proxy_connect headers rewrite

Overwrite :file:`/etc/apache2/sites-available/000-default.conf` with the following::

    <VirtualHost *:443>
      SSLEngine on
      SSLProxyEngine on
      SSLCertificateFile /etc/apache2/ssl/certs/numbas_lti.crt
      SSLCertificateKeyFile /etc/apache2/ssl/private/numbas_lti.key

      ProxyPreserveHost On
      ProxyRequests Off
      ProxyPass /static !
      Alias "/static" "/srv/numbas-lti-static"
      ProxyPass /media !
      Alias "/media" "/srv/numbas-lti-media"
      ProxyPass "/websocket" "ws://0.0.0.0:8700/websocket"
      ProxyPassReverse "/websocket" "ws://0.0.0.0:8700/websocket"
      ProxyPass / http://0.0.0.0:8700/
      ProxyPassReverse / http://0.0.0.0:8700/

      RequestHeader set X-Scheme "https"
      RequestHeader set X-Forwarded-Proto "https"

      <Directory "/srv/numbas-lti-static">
        AllowOverride None
        Options FollowSymLinks
        Require all granted
      </Directory>

      <Directory "/srv/numbas-lti-media">
        AllowOverride None
        Options FollowSymLinks
        Require all granted
      </Directory>

      ErrorLog ${APACHE_LOG_DIR}/numbas_lti.error.log
      CustomLog ${APACHE_LOG_DIR}/numbas_lti.access.log combined
    </VirtualHost>

Set the ``SSLCertificateFile`` and ``SSLCertificateKeyFile`` lines to the paths to your SSL certificate and key files.
If you're using certbot, it will add those lines for you.

Obtain an SSL certificate
-------------------------

An SSL certificate allows your server to communicate with browsers securely.

The easiest way of obtaining an SSL certificate is with `certbot <https://certbot.eff.org/>`_, from the EFF.
It's a command-line tool which automatically acquires certificates from `Let's Encrypt <https://letsencrypt.org/>`_ for any domains you're serving.
Follow the instructions on the certbot site, after setting up your web server, to obtain a certificate.

These certificates don't last very long, and need to be renewed.
You can do this automatically by running ``certbot renew`` as a cron job; put the following in :file:`/etc/cron.daily/renew-certbot`::

    #!/bin/sh
    certbot renew

Make sure that :file:`/etc/cron.daily/renew-certbot` is executable by the root user::

    chmod +x /etc/cron.daily/renew-certbot

If you have no other way of obtaining a certificate, you can `create a self-signed certificate <https://help.ubuntu.com/lts/serverguide/certificates-and-security.html.en#creating-a-self-signed-certificate>`_ which will produce a security warning in web browsers.

Ensure outcome reporting works
------------------------------

In order to report scores back to the :term:`tool consumer <Tool consumer>`, the Numbas LTI provider must make an HTTPS request to an address provided by the consumer.
Normally, this is on the same domain as the consumer.

Ensure that the machine on which the LTI provider is running can make HTTPS requests to the consumer - if you're working in a testing environment, you may need to configure the consumer's server to allow connections on port 443 from the provider's IP address.

Updating the software
---------------------

You should keep the software up-to-date with any bugfixes or new features.

Run the following::

    cd /srv/numbas-lti-provider
    git pull origin
    source /opt/numbas_lti_python/bin/activate
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py collectstatic --noinput
    supervisorctl restart numbas_lti:

Ready to use
------------

Once you've got everything running, the LTI provider will be available to use, at the domain name you configured.

Open the site in a web browser and log in using the admin account credentials you set up earlier.

If you encounter any problems, see the :ref:`installation-troubleshooting` page.

The next step is to add an LTI consumer key so that your VLE can connect to the LTI provider.
