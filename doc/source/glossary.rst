Glossary
========

.. glossary::

    LTI
        Learning Tools Interoperability is a standard which defines how a :term:`tool consumer` connects to a :term:`tool providing <tool provider>` a learning activity.
        The consumer can provide some information about the person who launched the activity, such as their name, their role in the course, and a unique identifier.
        The :term:`tool provider` can report back a score after a user has completed the activity.

    VLE
        A Virtual Learning Environment, such as Blackboard, Moodle or Canvas.

    Tool consumer
        A system from which users launch LTI activities, such as a :term:`VLE`.

    Tool provider
        A system which provides activites to :term:`tool consumers <tool consumer>`.

    Resource
        In the Numbas LTI provider, each link from a tool consumer to the provider creates a new resource, representing a single exam to be completed by students.

    Attempt
        A student may make one or more attempts at a :term:`resource`.
        Each attempt is independent from the others.

    Editor link
        A connection between the LTI provider and an instance of the Numbas editor.
