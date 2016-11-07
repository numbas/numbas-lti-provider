<img src="http://numbas.org.uk/numbas-logo.svg" width="100%" alt="Numbas logo">

# LTI tool provider

This is a Basic LTI 1.1 tool provider, to run [Numbas](http://www.numbas.org.uk) exams in any LTI-compatible virtual learning environment.

The tool handles attempt data, and as well as offering CSV exports of student scores can report scores back to the host VLE's gradebook.

## How to use

You must run your own instance of this tool - as well as using a fair amount of server resources, we don't want to keep other people's student data!

The set-up process looks like this:

* Install the software on your own server, or on the cloud platform Heroku.
* Complete the initial set-up, creating an admin account and an LTI consumer key.
* Add the LTI tool to your VLE using the details provided.

## Installing the software

### In the cloud with Heroku

The quickest way of setting up the software is through Heroku. Click on the button - it'll take about five minutes from start to finish.

[![Deploy Numbas LTI tool provider to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/numbas/numbas-lti-provider/tree/heroku)

### In a Vagrant virtual machine

[Vagrant](https://www.vagrantup.com/) provides an easy way of managing virtual machines on your computer. You might want to use this if you're trying out the software on a Windows PC, or want to run the tool in a self-contained environment, separate from your other software.

*I set up Vagrant to forward port 443 on the host machine to port 443 on the VM. I think this might only work on Windows. I'm not sure how to get it running on a different port - I had problems with the nginx proxy.*

Create a directory for the vagrant VM:

```
mkdir numbas_lti
cd numbas_lti
```

Edit `Vagrantfile`:

```
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "ubuntu/xenial64"

  config.vm.network :forwarded_port, host: 443, guest: 443
end
```

Start vagrant and ssh into it:

```
vagrant up
vagrant ssh
```

Once you've got a shell on the VM, follow the "on your own server" installation instructions below.

### On your own server

* [Using Apache on Ubuntu 16.04](doc/install_apache.md)

## Complete the set-up

Open the tool's homepage in your browser. You'll be guided through the process of setting up an admin account and adding a consumer key to the database.

Once that's done, you'll see something like the following:

!["Manage consumers" screen](doc/manage_consumers.png)

That page shows the three pieces of information you need to give to your VLE: the **launch URL**, the **consumer key** and the **shared secret**.

## Add the tool to your VLE

The final step is to create a link between your VLE and the tool provider.

### With Blackboard

Follow Blackboard's instructions ["How to add a new Basic LTI tool provider"](http://library.blackboard.com/ref/df5b20ed-ce8d-4428-a595-a0091b23dda3/Content/_admin_app_system/admin_app_basic_lti_tool_providers.htm). 

* The **Provider domain** is your launch URL.
* The **Tool provider key** is your consumer key.
* The **Tool provider secret** is your shared secret.

### With Moodle

The following instructions apply to Moodle 3.0. In earlier versions of Moodle, the names and organisation of the settings pages are different, but the fields you need to enter are largely the same.

If you have administrator privileges on Moodle, you can add the tool as an activity type, so you don't have to enter the settings for each exam.

* Go to Site administration -> Plugins -> Activity modules -> External tool -> Manage tools.
* Click on "configure a tool manually".
* Set **Tool name** to "Numbas".
* The **Tool base URL** is your launch URL.
* The **Consumer key** is your consumer key.
* The **Shared secret** is your shared secret.
* Under *Tool configuration usage*, select "Show in activity chooser when adding an external tool".

Now you can add a Numbas exam in any course by clicking "Add an activity or resource" and selecting "Numbas".
