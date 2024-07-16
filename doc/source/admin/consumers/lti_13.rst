.. _add-lti-13-consumer:

Adding an LTI 1.3 platform
##########################

Click the :guilabel:`Add a new LTI 1.3 consumer` button.

The next steps depend on your consumer platform.
Platforms that support dynamic registration are fairly straightforward.

At the moment, Canvas does not support dynamic registration at all, and Blackboard requires a separate registration with their developer portal.

Follow the instructions for your platform; the page gives you the necessary details pertaining to your server.

.. _lti-13-dynamic-registration:

Dynamic registration
--------------------

If your platform supports it, dynamic registration is the easiest.

You first create a registration token, which is a URL you'll give to the consumer platform.

When you give the token to the consumer platform, you'll be asked to confirm that you want to use it to link to this platform.

After confirming, the registration is carried out automatically.

Some platforms might need further steps, such as activating the registration or managing where it can be used.

Moodle
------

Moodle supports dynamic registration.

`Create a dynamic registration token <lti-13-dynamic-registration>`, and then in Moodle go to :guilabel:`Site administration` → :guilabel:`Plugins` → :guilabel:`External tool` → :guilabel:`Manage tools`.

Paste the token URL into the :guilabel:`Tool URL` field, and click on :guilabel:`Add LTI Advantage`.

After clicking the :guilabel:`Register` button to confirm you want to use the token, the registration is complete.

You must activate the Numbas LTI external tool in Moodle before it can be used.

Blackboard
----------

Blackboard expects most LTI tools to run on a single domain, which serves every institution using it.

Because each institution runs their own instance of the Numbas LTI tool, each instance must be registered separately with Anthology.

Follow the instructions shown in the Numbas interface to register with Anthology, then add the app within your Blackboard environment.

Once that's done, you'll have a :guilabel:`Client ID` and :guilabel:`Deployment ID` that you can put into the form at the end of the Numbas Blackboard registration page to complete the process.

Canvas
------

We haven't yet tested dynamic registration with Canvas.

The instructions in the Numbas interface take you through the process of using a JSON configuration URL to add the tool to Canvas.
