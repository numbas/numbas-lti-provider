Migrating to Docker
###################

These instructions describe how to move from an existing server running the LTI provider on Ubuntu, to the Docker version.

They have been run once, by Christian Lawson-Perfect, and not tested by anyone else yet.
Some changes might be necessary when you follow this.

If you encounter problems at any stage, please `tell us about them <mailto:numbas@ncl.ac.uk>`__.

Plan
----

There are two collections of data that need to be copied from the old server to the new: the database, and the media folder.

If you followed the installation instructions exactly, the database is held in PostgreSQL, and the media files are in ``/srv/numbas-lti-media``.

The Numbas LTI Provider Docker system sets up three *volumes*, where Docker stores its data: one for the PostgreSQL database, one for Redis, and one for the media.

To copy the database over, use postgres's dump and restore methods.

The media files can be copied directly into the corresponding Docker volume.

On the original server
----------------------

Dump the database to a file::

    sudo -u numbas_lti pg_dump numbas_lti > /tmp/numbas_lti.psql

Compress the uploaded media::

    cd /srv
    tar czf /tmp/numbas_lti_media.tar.gz numbas-lti-media

Copy the files ``/tmp/numbas_lti.psql`` and ``/tmp/numbas_lti_media.tar.gz`` to the machine which will run the Docker containers.

On the machine running Docker
-----------------------------

Open a terminal in the ``numbas-lti-provider-docker`` directory.

Stop the docker containers, if they're running::

    docker-compose down

Remove any existing database::

    docker volume rm numbas-lti-provider-docker_pgdata

Restart the docker containers. 
This will recreate the volume for the postgres database::

    docker-compose up

Restore the database dump to the postgres volume (``numbas_lti.psql`` is the database dump created on the old server)::

    cat numbas_lti.psql | docker-compose exec -T postgres psql -U numbas_lti

Decompress the media files (``numbas_lti_media.tar.gz`` is the compressed media folder created on the old server)::

    tar xzf numbas_lti_media.tar.gz

Find out where the numbas docker volume is on disk::

    docker volume inspect numbas-lti-provider-docker_numbas

The ``Mountpoint`` value in the output is the location on disk of the numbas volume.

Set the environment variable ``MOUNTPOINT`` to this path::

    export MOUNTPOINT=...

Copy the media files to the volume::

    sudo cp -r numbas-lti-media $MOUNTPOINT

I had to change the permissions on the copied directory::

    sudo chmod -R 777 $MOUNTPOINT/numbas-lti-media

That's it!
