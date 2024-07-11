.. _upgrading-installation:

Upgrading to a new version
##########################

When upgrading the Numbas LTI provider, follow the upgrade instructions for your platform.

Sometimes new versions of the LTI provider require changes that can't be made automatically by the normal upgrade procedure.

For such releases, this page lists the changes that must be made.

v4.0
----

Docker installation
^^^^^^^^^^^^^^^^^^^

There are no special upgrade steps for Docker installations for this version.

Non-Docker installation
^^^^^^^^^^^^^^^^^^^^^^^

The stable git branch for this version is ``v4_STABLE``.

The minimum required version of Python is now 3.10.

There are changes to some values in :file:`settings.py`, and new settings ``CACHES`` and ``REQUESTS_USER_AGENT``.

Add the following line to the top of :file:`numbasltiprovider/settings.py`::

    import pylti1p3.roles

Copy the values of the following objects from :file:`numbasltiprovider/settings.py.dist` to :file:`numbasltiprovider/settings.py`:

* ``INSTALLED_APPS`` (adding ``'daphne'`` and ``'numbas_lti.apps.PyLTI1p3ToolConfigBigAutoField'``)
* ``AUTHENTICATION_BACKENDS`` (replacing ``'numbas_lti.backends.LTIAuthBackend'`` with ``'numbas_lti.backends.LTI_11_AuthBackend'`` and ``'numbas_lti.backends.LTI_13_AuthBackend'``)
* ``STORAGES`` (replaces ``STATICFILES_STORAGE``)
* ``LTI_INSTRUCTOR_ROLES`` (there are separate lists for LTI 1.1 and LTI 1.3)
* ``CACHES`` (new setting)
* ``REQUESTS_USER_AGENT`` (new setting)
* ``CANVAS_LTI_13_PRESETS`` (new setting)

v3.2
----

Docker installation
^^^^^^^^^^^^^^^^^^^

There is a new setting for the :ref:`lockdown app <lockdown-apps>` support:

* ``NUMBAS_LOCKDOWN_APP_PASSWORD`` - a default password to use with the Numbas lockdown app.

Non-Docker installation
^^^^^^^^^^^^^^^^^^^^^^^

There are new settings for the :ref:`lockdown app <lockdown-apps>` support.
Copy the ``LOCKDOWN_APP`` setting from :file:`numbasltiprovider/settings.py.dist` into :file:`numbasltiprovider/settings.py`, and change the ``'password'`` value.

The installation instructions now recommend you regularly run the ``clearsessions`` command. 
See :ref:`maintenance-cron-jobs`.

v3.0
----

Docker installation
^^^^^^^^^^^^^^^^^^^

There are a few new settings which must be present in :file:`settings.env`.
See :ref:`server-settings` for information on the values these settings should take.

* ``INSTANCE_NAME``
* ``TIME_ZONE``
* ``DEFAULT_FROM_EMAIL``
* ``SUPPORT_NAME``
* ``SUPPORT_URL``
* ``EMAIL_COMPLETION_RECEIPTS``

Non-Docker installation
^^^^^^^^^^^^^^^^^^^^^^^

This version updates many of the packages that the LTI tool relies on, and so introduces quite a few changes to the way that the tool is configured.

The minimum required versions of some software have increased:

* Python 3.8 or newer
* Redis 5 or newer

Git branch
**********

There are now stable git branches for each major version of the LTI provider.
When upgrading to v3.0, switch to the ``v3_STABLE`` branch::

    cd /srv/numbas-lti-provider
    git fetch origin
    git checkout v3_STABLE

After this, you can proceed with the rest of the update steps for your system.
For Ubuntu, the next command will be ``source /opt/numbas_lti_python/bin/activate``.

Packages to install
********************

There are changes to the required versions of packages specified in :file:`requirements.txt`.
In addition, if you are using Redis as the Channels backend, you will need to install ``channels_redis``::

    pip install channels_redis==3.3.1

Supervisor configuration
************************

Overwrite the configuration for ``supervisord`` with the new one given in the installation instructions for your system: :ref:`Ubuntu <ubuntu-configure-supervisord>`, :ref:`RHEL 7 <rhel-7-configure-supervisord>`.

The ``numbas_lti_worker`` processes are no longer needed, and the command to launch the ``numbas_lti_daphne`` processes has changed.

Changes to settings
*******************

There are several changes to make in the file :file:`numbasltiprovider/settings.py`.

The template file, :file:`numbasltiprovider/settings.py.dist`, has been rearranged and lots of comments added to better explain what the settings do.
You might like to use that file as a base, and insert your existing settings, rather than just changing your existing file.

* The way that Channels is configured has changed.
  To use Redis as the backend, replace the ``CHANNEL_LAYERS`` setting with the following::

      CHANNEL_LAYERS = {
          "default": {
              "BACKEND": "channels_redis.core.RedisChannelLayer",
              "CONFIG": {
                  "hosts": [os.environ.get('REDIS_URL','redis://localhost:6379')],
              }
          },
      }

  For other backends, see the `Channels documentation <https://channels.readthedocs.io/en/stable/topics/channel_layers.html>`__.

* Django now requires the ``DEFAULT_AUTO_FIELD`` setting to be set as follows::

      DEFAULT_AUTO_FIELD='django.db.models.AutoField'

* If you are using MySQL for your database, add the following underneath inside the ``'default'`` entry in the ``DATABASES`` setting, in order to improve handling of Unicode characters::

      'OPTIONS': {
          'charset': 'utf8mb4',
          'use_unicode': True,
      },

  You might need to convert the tables within MySQL to use the ``utf8mb4`` character set and ``utf8mb4_unicode_ci`` collation rules.
  See `this post by Mathias Bynens <https://mathiasbynens.be/notes/mysql-utf8mb4>`__ for instructions on how to do that.

* The Huey task runner now prioritises tasks. 
  Change the ``HUEY`` setting to the following::

      HUEY = {
          'huey_class': 'huey.PriorityRedisHuey',
      }

* Add ``'numbas_lti.context_processors.global_settings'`` to the ``TEMPLATES['OPTIONS']['context_processors']`` setting.

* There is a new setting ``INSTANCE_NAME``, which should contain the name of the server, to display to users.
  If the server is run by the University of Somewhere, you might set::

    INSTANCE_NAME = 'University of Somewhere'

* There is a new setting ``REPORT_FILE_EXPIRY_DAYS``, specifying the number of days that report files should remain available, before being deleted.
  The recommended length of time to keep reports is 30 days::

      REPORT_FILE_EXPIRY_DAYS = 30

* Remove ``'django_cookies_samesite.middleware.CookiesSameSite'`` from ``MIDDLEWARE``.

v2.13
-----

There was an error in the base :file:`settings.py` file when localisation was introduced. 

If you are using the English translation, in :file:`numbasltiprovider/settings.py`, change ``LANGUAGE_CODE = 'en-us'`` to ``LANGUAGE_CODE = 'en'``. 

v2.11
-----

This release adds a dependency on the `django-statici18n <https://django-statici18n.readthedocs.io/en/latest/index.html>`_ package to translate dynamically-generated text.

In :file:`numbasltiprovider/settings.py`, add ``'statici18n'`` to ``INSTALLED_APPS``. 

The whole list should now be::

    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'channels',
        'huey.contrib.djhuey',
        'statici18n',
        'numbas_lti',
        'bootstrapform',
        'bootstrap_datepicker_plus',
    ]

v2.10
-----

This release uses the task runner `huey <https://github.com/coleifer/huey>`_ to perform long-running tasks.

In :file:`numbasltiprovider/settings.py`, add ``'huey.contrib.djhuey`` to ``INSTALLED_APPS``. 

The whole list should now be::
    
    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'channels',
        'huey.contrib.djhuey',
        'numbas_lti',
        'bootstrapform',
        'bootstrap_datepicker_plus',
    ]

Add a huey process to the supervisord configuration (in :file:`/etc/supervisor/conf.d/numbas_lti.conf` on Ubuntu)::

    [program:numbas_lti_huey]
    command=/opt/numbas_lti_python/bin/python /srv/numbas-lti-provider/manage.py run_huey -w 8
    directory=/srv/numbas-lti-provider/
    user=numbas_lti
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
    programs=numbas_lti_daphne,numbas_lti_workers,numbas_lti_huey
    priority=999

Note that the ``[group:numbas_lti]`` section has changed as well.
