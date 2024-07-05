.. _installation_docker:

Installation with Docker
########################

You will need:

* Access to a server where you can run `Docker <https://www.docker.com/>`_ and `Docker Compose <https://docs.docker.com/compose/>`_. 
  A virtual machine is fine.
* A domain name pointed at the server you're going to use. 
  A subdomain (e.g. ``numbas-lti.youruniversity.edu``) is fine.
* An SSL certificate: LTI content must be served over HTTPS. 
  These can be obtained easily and for free from `Let's Encrypt <https://letsencrypt.org/>`_.

These instructions will run the Numbas LTI provider inside a Docker container, along with containers for the services it requires.

Setup
-----

Obtain the Docker compose recipe and its associated files either by `downloading the latest release from GitHub <https://github.com/numbas/numbas-lti-provider-docker/releases>`_, or by cloning the git repository::

    git clone https://github.com/numbas/numbas-lti-provider-docker.git

Build the docker image::

    docker build . -t numbas/numbas-lti-provider

Copy the file :file:`settings.env.dist` to :file:`settings.env` and write your own values for each of the variables inside.

Run the ``get_secret_key`` script to generate a value for the ``SECRET_KEY`` environment variable, and put that in :file:`settings.env`::

    docker compose run --rm numbas-setup python ./get_secret_key

Obtain an SSL certificate and key for the domain you will access the Numbas LTI provider from. 
Copy the key to :file:`files/ssl/numbas-lti.key` and the certificate to :file:`files/ssl/numbas-lti.pem`.

Run the installation script, to set up the database and create the superuser account::

    docker compose run --rm numbas-setup python ./install

The LTI provider is ready to start.

Starting
--------

Run the following command::

    docker compose up --scale daphne=4 --scale huey=2

You can customise the number of each of the kinds of process by changing the numbers in the `--scale` arguments.
You'll have to establish how many of each you need by experimentation.
The `daphne` process handles web requests; you will need more if you have lots of simultaneous connections.
The `huey` process runs asynchronous tasks; you will need more if you find that tasks such as reporting scores or generating report files take a very long time.

Stopping
--------

Stop the containers with::

    docker compose down

This does not delete any permanent data such as the database, settings file or uploaded files.

Upgrading
---------

When there is a new version of the Numbas LTI provider, you must rebuild the Docker image and apply any database migrations.

If any other changes are required when moving to a particular version, they will be listed on the :ref:`upgrading-installation` page.

First, update the files in the Docker repository.
If you used git, run::

    git pull

Remake the container image::

    docker build . --no-cache -t numbas/numbas-lti-provider

Then run the installation script again:

    docker compose run --rm numbas-setup python ./install

Finally, restart the containers::

    docker compose restart

Running in the cloud
--------------------

Docker Compose files can also be used to deploy to the cloud.
See the following documents for more information about deploying Docker to the cloud:

* `Compose for Amazon ECS <https://docs.docker.com/engine/context/ecs-integration/>`_
* `Compose for Microsoft ACI <https://docs.docker.com/engine/context/aci-integration/)>`_
