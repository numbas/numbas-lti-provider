Getting started
===============

This document will lead you through the process of setting up an instance of the Numbas LTI tool provider on your own server, and adding a Numbas activity to a course in your VLE.

What do I need in order to use this?
####################################

You must run your own instance of this tool - as well as using a fair amount of server resources, we don't want to keep other people's student data!

To install the tool, you need:

* A dedicated server to install the software on, which will communicate with your virtual learning environment. 
  At Newcastle, we use servers running Ubuntu. 
* The ability to add a link to an LTI tool to your virtual learning environment. 
  In Blackboard and Moodle, only administrators can do this.

At most institutions, this will require the help of your IT team.

If you're unsure whether you can use the LTI tool provider, or want help setting it up, `email the Numbas team <mailto:numbas@ncl.ac.uk>`_.

Install the software
####################

Follow the :ref:`installation instructions <installation>` to set up an instance of the Numbas LTI tool provider on your own server.

Link your VLE
#############

:ref:`Create a consumer <add-consumer>` in the tool provider's admin interface, and connect to it from your VLE.

This may require support from the administrator of your VLE.

Link a Numbas editor
####################

You can :ref:`link to an instance of the Numbas editor <add-editor-link>` to make a selection of exams available directly from the LTI tool, instead of having to download a Numbas exam package to your own computer first.

Add a Numbas activity to your course
####################################

:ref:`Add a link <create-resource>` from your course's page in your VLE to the Numbas tool provider.

Download a Numbas exam package from `the Numbas editor <https://numbas.mathcentre.ac.uk>` and upload it to the newly-created resource.

Students who click on the link will be shown the exam, and their answers and scores will be saved to the tool provider.

Get scores for the activity
###########################

You can :ref:`download a .CSV file<download-scores>` of the students' scores  or :ref:`report their scores back to the VLE's gradebook<report-scores>`.
