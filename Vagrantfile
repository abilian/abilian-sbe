# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/trusty64"

  config.vm.provider :virtualbox do |vb|
    vb.memory = 1024
    vb.cpus = 2
  end

  config.vm.network "forwarded_port", guest: 5000, host: 5000

  config.vm.provision :shell, :path => "deploy/provision.sh"
end
