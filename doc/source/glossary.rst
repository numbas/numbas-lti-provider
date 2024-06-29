Glossary
========

.. glossary::

    Attempt
        A student may make one or more attempts at a :term:`Resource`.
        Each attempt is independent from the others.

    Editor link
        A connection between the LTI provider and an instance of the Numbas editor.
        See :ref:`editorlink`.

    LTI
        Learning Tools Interoperability is a standard which defines how a :term:`Tool consumer` connects to a :term:`tool providing <Tool provider>` a learning activity.
        The consumer can provide some information about the person who launched the activity, such as their name, their role in the course, and a unique identifier.
        The :term:`Tool provider` can report back a score after a user has completed the activity.

    Resource
        In the Numbas LTI provider, each link from a tool consumer to the provider creates a new resource, representing a single exam to be completed by students.
        See :ref:`resources`.

    Tool consumer
        A system from which users launch LTI activities, such as a :term:`VLE`.
        See :ref:`consumer`.

    Tool provider
        A system which provides activites to :term:`tool consumers <Tool consumer>`.
        The Numbas LTI software is a tool provider.

    Platform
        In the LTI 1.3 standard, what we call a :term:`Tool consumer` is now called a *Platform*.

    SCORM
        `Sharable Content Object Reference Model <https://scorm.com/scorm-explained/>`__.

        Numbas exam packages are SCORM packages, and the Numbas LTI provider acts as a SCORM player.

    SEB
        `Safe Exam Browser <https://safeexambrowser.org>`_.

        See :ref:`the documentation on Safe Exam Browser <safe-exam-browser>`.

    VLE
        A Virtual Learning Environment, such as Blackboard, Moodle or Canvas.
        Also known as a Learning Management System, or LMS.
