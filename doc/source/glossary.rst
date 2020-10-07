Glossary
========

.. glossary::

    LTI
        Learning Tools Interoperability is a standard which defines how a :term:`Tool consumer` connects to a :term:`tool providing <Tool provider>` a learning activity.
        The consumer can provide some information about the person who launched the activity, such as their name, their role in the course, and a unique identifier.
        The :term:`Tool provider` can report back a score after a user has completed the activity.

    VLE
        A Virtual Learning Environment, such as Blackboard, Moodle or Canvas.
        Also known as a Learning Management System, or LMS.

    Tool consumer
        A system from which users launch LTI activities, such as a :term:`VLE`.
        See :ref:`consumer`.

    Tool provider
        A system which provides activites to :term:`tool consumers <Tool consumer>`.
        The Numbas LTI software is a tool provider.

    Resource
        In the Numbas LTI provider, each link from a tool consumer to the provider creates a new resource, representing a single exam to be completed by students.
        See :ref:`resources`.

    Attempt
        A student may make one or more attempts at a :term:`Resource`.
        Each attempt is independent from the others.

    Editor link
        A connection between the LTI provider and an instance of the Numbas editor.
        See :ref:`editorlink`.
