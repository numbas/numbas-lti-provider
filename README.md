<img src="http://numbas.org.uk/numbas-logo.svg" width="100%" alt="Numbas logo">

# LTI tool provider

This is a Basic LTI 1.1 tool provider, to run [Numbas](http://www.numbas.org.uk) exams in any LTI-compatible virtual learning environment.

The tool handles attempt data, and as well as offering CSV exports of student scores can report scores back to the host VLE's gradebook.

## What do I need in order to use this?

You must run your own instance of this tool - as well as using a fair amount of server resources, we don't want to keep other people's student data!

To install the tool, you need:

* A dedicated server to install the software on, which will communicate with your virtual learning environment. At Newcastle, we use servers running Ubuntu. 
* The ability to add a link to an LTI tool to your virtual learning environment. In Blackboard and Moodle, only administrators can do this.

At most institutions, this will require the help of your IT team.

If you're unsure whether you can use the LTI tool provider, or want help setting it up, [email the Numbas team](mailto:numbas@ncl.ac.uk).

## How to use

The set-up process looks like this:

* Install the software on your own server, or on the cloud platform Heroku.
* Complete the initial set-up, creating an admin account and an LTI consumer key.
* Add the LTI tool to your VLE using the details provided.
* When you access the tool from your VLE, upload a Numbas SCORM package, and you're done!

## Documentation

See [full documentation at docs.numbas.org.uk/lti](https://docs.numbas.org.uk/lti).
