.. _stress-tests:

Stress tests
############

Use the stress test feature to see how the LTI provider copes with high demand.
You can use this to identify potential problems before any sessions where you expect many students to be attempting a Numbas exam at the same time.

During a stress test, each device taking part will open multiple connections to the LTI provider and simulate sending attempt data.

Running a stress test
---------------------

To begin a new stress test, click the :guilabel:`Start a stress test` button.
You will be taken to the stress test control panel.

On each device taking part in the test, log in to the Numbas LTI provider's admin interface and navigate to the stress test's control panel.

You can simulate a single attempt by clicking the :guilabel:`Start an attempt` button.
Each simulated attempt will open a connection from your device to the LTI provider, and send a new data element at the rate specified by the :guilabel:`Set new elements every __ seconds` field.

You can start multiple attempts at the same time with the first line of the form.
Click the :guilabel:`now` button to start some attempts immediately, or enter a time - you could use this to coordinate several devices.

.. caution::

    Many web browsers have a limit on the number of websocket connections they can hold open at once.

    At time of writing, Chrome is limited to 255 simultaneous connections, Firefox to 200, and Internet Explorer is limited to 6.

    If you simulate more attempts than this, the extra attempts will use the AJAX fallback.

You can change the rate at which new elements are set, and the number of elements set when each attempt starts.

A Numbas exam normally sets around 100 elements when an attempt starts.
This number grows slightly for exams with more questions and question parts.

When a student submits an answer, three or four elements are set.
So, a "realistic" value for the :guilabel:`Set new elements every __ seconds`` field will be around :math:`\frac{\text{total attempt time}}{5 \times (\text{number of parts})}`.

Interpreting the results of a stress test
-----------------------------------------

Summary is shown above the list of all simulated attempts.
This is only for the attempts being simulated on your device - because the point of the test is to identify bottlenecks in the network, there's no reliable way of showing data about all devices taking part in the test.
For each attempt, the current state of the connection, and the number of elements unsaved, are shown.

All attempts should have finished "waiting to start" within a minute or so of the test beginning.

Ideally, there should be zero attempts without a websocket connection.
Attempts without a websocket connection will use the AJAX fallback, which saves data less regularly.

The most important statistic is the number of attempts with unsaved data.
If this number remains above 0 for a long time, it means that the server has a backlog of data to save.
In a real test, each device will keep resending data until it gets an acknowledgement that it has been saved, so data will eventually be recorded, if slowly.

If the connection is lost entirely - for example, if there's a power cut, the student's computer crashes, or the student closes the test before all data has been saved - any data which has not been acknowledged by the server will be saved to the browser's local storage on the student's machine.
When the student reopens the test, any data in local storage will be sent.

If an attempt shows :guilabel:`AJAX is not working`, then a request to use the AJAX fallback has failed: usually because the connection timed out or was refused entirely.
This is a sign that the LTI provider can not cope with the amount of traffic you're simulating, and students would see errors or data might go missing in a real test.
