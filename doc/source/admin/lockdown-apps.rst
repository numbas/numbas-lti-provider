.. _lockdown-apps:

Lockdown apps
#############

Numbas supports two kinds of lockdown app, to ensure students can only access resources in a controlled environment.

The :guilabel:`Lockdown apps` admin page allows you to configure these apps.

Numbas lockdown app
===================

The `Numbas lockdown app <http://www.numbas.org.uk/lockdown-app/>`_ is made for launching exams from the Numbas LTI provider.

Students should go to http://www.numbas.org.uk/lockdown-app/ to install the appropriate version of the app on their device.
There are versions of the app for Windows, Linux, macOS and iOS.
An Android version is in development.

When a student launches a resource which requires the Numbas app, they will be prompted for a password to decrypt the launch settings.

The default password is defined by the ``LOCKDOWN_APP['password']`` setting in :file:`numbasltiprovider/settings.py`.
Instructors can specify a different password on individual resources.

Safe Exam Browser
=================

`Safe Exam Browser <https://safeexambrowser.org/news_en.html>`__ (SEB) is a generic locked-down browser app for running exams in a controlled environment.
It is usually used to prevent the student from accessing other programs while completing an exam.

Students should go to https://safeexambrowser.org/download_en.html to download the right version of the Safe Exam Browser app for their device.
There are versions of SEB for Windows, macOS and iOS.

The Safe Exam Browser client is configured with a settings file.
You must upload a settings file to the Numbas LTI provider in order to require that a resource runs through SEB.

Adding a Safe Exam Browser settings file
----------------------------------------

In the LTI provider, click the :guilabel:`Manage SEB settings files` link, and then click :guilabel:`Add a new SEB settings file`.

You are given values to enter in the SEB config tool's :guilabel:`Start URL` and :guilabel:`Link to quit SEB after exam` field.

See `the Safe Exam Browser configuration documentation <https://safeexambrowser.org/windows/win_usermanual_en.html#configuration>`__ for more information on how SEB can be configured.

Once you have created a settings file, copy the :guilabel:`Configuration key` from the configuration tool's :guilabel:`Exam` tab into the Numbas LTI provider form.

If you set a :guilabel:`Settings password` and would like to show it to students when they launch a resource, you should also copy the password into the Numbas LTI provider form.

Attach the ``.seb`` settings file to the form, and click :guilabel:`Add SEB settings`.

Requiring a lockdown app to launch a resource
=============================================

Instructors can require either the Numbas lockdown app or Safe Exam Browser to be used when a student launches a resource.

See :ref:`require-lockdown-app` for information on how an instructor can require a lockdown app for a resource.

When a student launches a resource requiring a lockdown app, they will be shown a button to launch the app, along with a link to install it if they haven't already.

Instructors are not required to use a lockdown app: they will be shown the instructor dashboard as normal.
