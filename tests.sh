#!/bin/bash

if [ `docker ps -f "name=influx-test" | wc -l` -gt 1 ]
then
    docker stop -t 0 influx-test
    docker rm influx-test
fi

docker run -d --name influx-test tutum/influxdb:0.9

docker run --rm --name alidron-archiver-unittest --link influx-test:db -v `pwd`:/workspace alidron/alidron-archiver-influxdb py.test -s --cov-report term-missing --cov-config /workspace/.coveragerc /workspace

if [ $? -eq 0 ]
then
    docker stop -t 0 influx-test
    docker rm influx-test
fi
