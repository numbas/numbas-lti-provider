.. _upgrading-installation:

Upgrading to a new version
##########################

When upgrading the Numbas LTI provider, follow the upgrade instructions for your platform.

Sometimes new versions of the LTI provider require changes that can't be made automatically by the normal upgrade procedure.

For such releases, this page lists the changes that must be made.

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
