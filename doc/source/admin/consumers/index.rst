.. _consumer:

Consumers
#########

A *tool consumer* is an application which sends users to the Numbas LTI provider, and receives score data in return.
In most cases, this will be a Virtual Learning Environment (VLE), such as Blackboard, Canvas or Moodle.

Only admin users on the LTI provider can create and manage consumers.

.. note::

    The terminology is slightly different in LTI 1.1 and LTI 1.3: 

    +---------------+----------+
    | LTI 1.1       | LTI 1.3  |
    +===============+==========+
    | Tool consumer | Platform |
    +---------------+----------+
    | Tool provider | Tool     |
    +---------------+----------+

    In the Numbas LTI provider, *consumer* refers to both an LTI 1.1 consumer and an LTI 1.4 platform.

The processes to register a consumer with the Numbas LTI provider differ for the LTI 1.1 and LTI 1.3 protocols.

.. toctree::
    :maxdepth: 1

    lti_13
    lti_11
    testing
    management
