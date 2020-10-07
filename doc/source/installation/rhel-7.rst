.. _installation-rhel-7:

Installation on RedHat Enterprise Linux 7
#########################################

.. note::

    These instructions were tested using a virtual machine running RedHat Enterprise Linux 7.8 on 2020-08-04.
    Software changes continually, so some steps might not work as described.

    If you have any trouble, please `file an issue on GitHub <https://github.com/numbas/numbas-lti-provider/issues>`_ or `email the Numbas team <mailto:numbas@ncl.ac.uk>`_.

You will need:

* Administrator access to a server with at least 4GB of RAM, connected to the internet. 
  A virtual machine is fine.
* A domain name pointed at the server you're going to use. 
  A subdomain (e.g. ``numbas-lti.youruniversity.edu``) is fine.
* An SSL certificate: LTI content must be served over HTTPS. 
  These can be obtained easily and for free from `Let's Encrypt <https://letsencrypt.org/>`_.

These instructions will take a fresh machine using RHEL 7 and set up the Numbas LTI tool provider to run through NGINX.
On different operating systems or with different web servers, the process will be different.
There are alternate instructions for :ref:`installation on Ubuntu <installation>`.

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

Make sure that your machine has an active subscription using :command:`subscription-manager`.

You may need to enable some extra repositories::

    subscription-manager repos --enable "rhel-*-optional-rpms" --enable "rhel-*-extras-rpms"  --enable "rhel-ha-for-rhel-*-server-rpms"

In order to install NGINX, create the :file:`/etc/yum.repos.d/nginx.repo` with the following contents::

    [nginx]
    name=nginx repo
    baseurl=http://nginx.org/packages/rhel/7/$basearch/
    gpgcheck=0
    enabled=1
    
Set up a user account and install packages, and create the required paths. 
Run the following commands as root::

    #!/bin/bash
    useradd numbas_lti
    yum install https://download.postgresql.org/pub/repos/yum/10/redhat/rhel-7-x86_64/pgdg-redhat-repo-latest.noarch.rpm
    yum install @development
    yum install postgresql96-server postgresql96 \
        python36 python36-pip python36-devel \
        python3-virtualenv \
        redis supervisor nginx git

    systemctl enable redis
    systemctl start redis

    # create media and static file directories
    mkdir /srv/numbas-lti-media
    mkdir /srv/numbas-lti-static
    chown -R numbas_lti:numbas_lti /srv/numbas-lti-media
    chown -R nginx:nginx /srv/numbas-lti-static
    chmod -R 770 /srv/numbas-lti-*

    # get the numbas-lti-provider code
    git clone https://github.com/numbas/numbas-lti-provider.git /srv/numbas-lti-provider
    chown -R numbas_lti:numbas_lti /srv/numbas-lti-provider

    # create the virtualenv for the python modules
    virtualenv-3 /opt/numbas_lti_python
    chown -R numbas_lti:numbas_lti /opt/numbas_lti_python
    chmod -R 770 /opt/numbas_lti_python

    # install python modules
    cd /srv/numbas-lti-provider
    source /opt/numbas_lti_python/bin/activate
    pip install -r requirements.txt
    pip install asgi_redis psycopg2-binary

Change PostgreSQL to use password authentication: edit :file:`/var/lib/psql/9.6/data/pg_hba.conf`, and change::

    host    all             all             127.0.0.1/32            ident

to::

    host    all             all             127.0.0.1/32            md5

Now restart PostgreSQL and create a database::

    systemctl restart postgresql-9.6
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

Once you've run this script, the last remaining steps are to start the app, and then set up a webserver to expose it to the outside world.

At this point, you can try running a development server to check that the Django part of the LTI provider is set up properly::

    python manage.py runserver

Access the development server at `http://localhost:8000`_.

Configure supervisord
---------------------

Supervisord ensures that the Numbas LTI provider app is always running.

Save the following as :file:`/etc/supervisord.d/numbas_lti.ini`::

    [program:numbas_lti_daphne]
    command=/opt/numbas_lti_python/bin/daphne numbasltiprovider.asgi:channel_layer --port 87%(process_num)02d --bind 0.0.0.0 -v 2
    directory=/srv/numbas-lti-provider/
    user=numbas_lti
    autostart=true
    autorestart=true
    stopasgroup=true
    environment=DJANGO_SETTINGS_MODULE=numbasltiprovider.settings
    numprocs=4
    process_name=%(program_name)s_%(process_num)02d
    stderr_logfile=/var/log/supervisor/numbas_lti_daphne_stderr.log
    stdout_logfile=/var/log/supervisor/numbas_lti_daphne_stdout.log

    [program:numbas_lti_workers]
    command=/opt/numbas_lti_python/bin/python /srv/numbas-lti-provider/manage.py runworker
    directory=/srv/numbas-lti-provider/
    user=numbas_lti
    autostart=true
    autorestart=true
    redirect_stderr=True
    stopasgroup=true
    environment=DJANGO_SETTINGS_MODULE="numbasltiprovider.settings"
    numprocs=10
    process_name=%(program_name)s_%(process_num)02d
    stderr_logfile=/var/log/supervisor/numbas_lti_workers_stderr.log
    stdout_logfile=/var/log/supervisor/numbas_lti_workers_stdout.log

    [group:numbas_lti]
    programs=numbas_lti_daphne,numbas_lti_workers
    priority=999

Once you've set this up, run::

    systemctl restart supervisord

Supervisord will start the Numbas LTI provider, and restart it automatically if it ever crashes.

Set up the NGINX webserver
--------------------------

`NGINX <https://www.NGINX.com/>`_ is a high performance webserver, ideal for use as a reverse proxy.
It is the recommended option for the Numbas LTI provider.

Add the `nginx` user to the `numbas_lti` group::

    usermod -a -G numbas_lti nginx

Overwrite :file:`/etc/nginx/conf.d/default.conf` with the following::

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

Finally, open the firewall to allow web traffic::

    setsebool -P httpd_can_network_connect 1
    firewall-cmd --permanent --zone=public --add-service=http
    firewall-cmd --permanent --zone=public --add-service=https
    firewall-cmd --reload
    setenforce permissive
    systemctl start nginx


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

Ensure that the machine on which the LTI provider is running can make HTTPS requests to the consumer - if you're working in a testing environment, you may need to configure the consumer's server to allow connections on 443 from the provider's IP address.

Updating the software
---------------------

You should keep the software up-to-date with any bugfixes or new features.

Run the following::

    cd /srv/numbas-lti-provider
    git pull origin master
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
