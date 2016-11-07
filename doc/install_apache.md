These instructions will take a fresh machine running Ubuntu 16.04 and set up the Numbas LTI tool provider to run through Apache. On different operating systems or with different web servers, the process will be different.

First, install packages and set up users:

* Run [setup_apache.sh](setup_apache.sh) to install packages and set up the environment.
* Install [letsencrypt](https://letsencrypt.org/) to obtain an SSL certificate, or [create a self-signed certificate](https://help.ubuntu.com/12.04/serverguide/certificates-and-security.html).
* Overwrite `/etc/apache2/sites-available/000-default.conf` with [apache.conf](apache.conf).
* Copy [settings.py](settings.py) to `/srv/numbas-lti-provider/pretendlti/settings.py`.
* Copy [asgi.py](asgi.py) to `/srv/numbas-lti-provider/pretendlti/asgi.py`.
* Copy [numbas_lti.conf](numbas_lti.conf) to `/etc/supervisor/conf.d/numbas_lti.conf`.
* Run [deploy.sh](deploy.sh) to set up the database and start the server.

The server is now running at `https://localhost`.

## Updating the software

You should keep the software up-to-date with any bugfixes or new features. Run [update.sh](update.sh) to update the software.
