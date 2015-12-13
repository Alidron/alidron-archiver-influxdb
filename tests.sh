#!/bin/bash

if [ `docker ps -f "name=influx-test" | wc -l` -gt 1 ]
then
    docker stop -t 0 influx-test
    docker rm influx-test
fi

docker run -d --name influx-test -p 8083:8083 -p 8086:8086 tutum/influxdb:0.9

sleep 1

docker run --rm --name alidron-archiver-unittest --link influx-test:db  -e PYTHONPATH=/usr/src/alidron-isac:/app/alidron-archiver alidron/alidron-archiver-influxdb py.test -s --cov-report term-missing --cov-config /app/alidron-archiver/.coveragerc --cov alidron_archiver -x /app

if [ $? -eq 0 ]
then
    docker stop -t 0 influx-test
    docker rm influx-test
fi
