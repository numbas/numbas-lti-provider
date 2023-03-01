.. _server-settings:

Settings
########

The settings for the server are configured in the file :file:`numbasltiprovider/settings.py`.

The :file:`first_setup.py` script creates this file on installation.
You might want to change settings if you have a nonstandard environment, or after upgrading.

The Numbas LTI provider is a Django app, so many of the settings come from Django.
See the `Django documentation <https://docs.djangoproject.com/en/3.2/ref/settings/>`__ for information on these.

This page describes the available settings which are unique to the Numbas LTI provider.

``INSTANCE_NAME``
-----------------

The name of this instance of the LTI provider.
You could use the name of your institution, or the name of the learning environment.

This is shown in the footer of each page.

``LTI_INSTRUCTOR_ROLES``
------------------------

A list of LTI role names which grant the user 'instructor' status if they're present.

See the `role vocabularies in the LTI spec <https://www.imsglobal.org/specs/ltiv1p0/implementation-guide#toc-6>`__.

``SUPPORT_NAME``
----------------

The name of your support contact.
This will be shown to students in case of errors.

``SUPPORT_URL``
---------------

A URL to direct students to when there is an error.
This could be a web address, a ``mailto:`` URI, or ``None`` if you don't want to display a link.

``EMAIL_COMPLETION_RECEIPTS``
-----------------------------

If this is ``True``, then the :ref:`email-receipts-option` option will be available for each resource.
Note that receipts are only sent for attempts at resources where the option is turned on by the instructor.

If this is ``False``, then no completion receipts will be sent for any resource.

The Numbas LTI provider uses Django's email system to send email through the SMTP protocol.
See the `Django documentation on sending email <https://docs.djangoproject.com/en/4.1/topics/email/>`__ for information about configuring this.
The relevant settings are `EMAIL_HOST <https://docs.djangoproject.com/en/4.1/ref/settings/#std-setting-EMAIL_HOST>`__, `EMAIL_PORT <https://docs.djangoproject.com/en/4.1/ref/settings/#std-setting-EMAIL_PORT>`__, `EMAIL_USER <https://docs.djangoproject.com/en/4.1/ref/settings/#std-setting-EMAIL_USER>`__ and `EMAIL_PASSWORD <https://docs.djangoproject.com/en/4.1/ref/settings/#std-setting-EMAIL_PASSWORD>`__.

``REQUEST_TIMEOUT``
-------------------

The number of seconds to wait when making an HTTP request to another service before giving up.

The following actions involve making HTTP requests to other services:

* Reporting scores back to the LTI consumer.
* Fetching updated exam packages from the Numbas editor
* Updating editor links.

``REPORT_FILE_EXPIRY_DAYS``
---------------------------

The number of days after which :ref:`report files <resource-reports>` should be deleted.

``HELP_URL``
------------

The address of the documentation for the LTI tool.

If this is not set, then the default of ``https://docs.numbas.org.uk/lti/en/<version>`` is used.
