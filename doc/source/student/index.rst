For students
============

When a student clicks on a link to launch a Numbas :ref:`activity <resources>` for the first time, they are taken straight into the exam.

Their answers and scores are saved as soon as they are submitted.

.. warning::
    
    Unsubmitted answers are not saved, so if the student's computer crashes, there will be no record of unsubmitted answers.
    It's important to make this clear to students during high-stakes tests, because they may want to wait until they've finished the whole question or exam before submitting.
    Numbas allows students to submit answers as many times as they like, with no penalty, so encourage them to submit as soon as they've entered an answer.

If the student leaves the test before completing it, they will be able to resume from where they left off next time they return.

On subsequent launches of the activity, the student is shown a summary of their attempts.
If :ref:`the exam's settings <when-to-show-scores>` allow it, the score earned for each attempt is shown.

The student can click the :guilabel:`Continue` button to resume an incomplete attempt where they left off.

Once a student clicks the :guilabel:`End exam` button, the attempt is marked as "completed", and the student can not change their answers.
If the server is configured to do it, the student is emailed a receipt containing information about their attempt, and a code that can be used by the instructor to :ref:`validate it <validate-receipt>`.

For completed attempts, the student can click :guilabel:`Review this attempt` to reopen the attempt in review mode, the same as was shown when they ended the exam.
They will see the results summary screen, and can click on individual questions to see their answers and any feedback.

If :ref:`the exam's settings <maximum-attempts>` allow it, or the student has an unused :ref:`access token <access-tokens>`, they can start a new attempt by clicking the :guilabel:`Start a new attempt` button.

.. figure:: _static/resume-attempt.png
    :alt: The student attempt summary screen. One incomplete attempt and one completed attempt are shown, along with their scores.

    The attempt summary screen shown to a student.
    
