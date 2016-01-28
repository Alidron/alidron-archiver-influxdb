InfluxDB archiver for Alidron
=============================

[![build status](https://git.tinigrifi.org/ci/projects/4/status.png?ref=master)](https://git.tinigrifi.org/ci/projects/4?ref=master) [![Gitter](https://badges.gitter.im/gitterHQ/gitter.svg)](https://gitter.im/Alidron/talk)

Made to work with InfluxDB 0.9+. Capable of doing time smoothing and archive or not based on the metadata of each IsacValue. It also buffers in case the DB cannot be reached anymore.

Docker containers
=================

The Docker images are accessibles on:
* x86: [alidron/alidron-archiver-influxdb](https://hub.docker.com/r/alidron/alidron-archiver-influxdb/)
* ARM/Raspberry Pi: [alidron/rpi-alidron-archiver-influxdb](https://hub.docker.com/r/alidron/rpi-alidron-archiver-influxdb/)

Dockerfiles are accessible from the Github repository:
* x86: [Dockerfile](https://github.com/Alidron/alidron-archiver-influxdb/blob/master/Dockerfile)
* ARM/Raspberry Pi: [Dockerfile](https://github.com/Alidron/alidron-archiver-influxdb/blob/master/Dockerfile-rpi)

Run
===

Instanciate an InfluxDB database. You don't need to setup the schemas or users, the archiver will do it at the first connection.

Make a copy of config_template.yaml and fill in the informations about the DB users, password and schema name you wish to use. If these are not already existing the root user information in the config file will be used to create them.

To start an archiver:
```
$ docker run -d --name=al-arch-influx -e DB_PORT_8086_TCP_ADDR=<YOUR DB IP> -e DB_PORT_8086_TCP_PORT=<YOUT DB PORT> -v `pwd`/buffer:/data alidron/alidron-archiver-influxdb python alidron_archiver.py your_config_file.yaml
```

You can start as many archiver as you want. Just be sure you change the `--name` parameter on Docker run command line.

License and contribution policy
===============================

This project is licensed under LGPLv3.

To contribute, please, follow the [C4.1](http://rfc.zeromq.org/spec:22) contribution policy.
