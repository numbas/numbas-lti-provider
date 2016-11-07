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

