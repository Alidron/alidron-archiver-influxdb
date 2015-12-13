#!/bin/bash

if [ `docker ps -f "name=influx-test" | wc -l` -gt 1 ]
then
    docker stop -t 0 influx-test
    docker rm influx-test
fi

docker pull tutum/influxdb:0.9
docker run -d --name influx-test -p 8083:8083 -p 8086:8086 tutum/influxdb:0.9

sleep 1

run_flags="--rm --name alidron-archiver-unittest --link influx-test:db -e PYTHONPATH=/usr/src/alidron-isac:/app/alidron-archiver"
exec_flags="py.test -s --cov-report term-missing --cov-config /app/alidron-archiver/.coveragerc --cov alidron_archiver /app"

if [ "$1" == "live" ]
then
    run_flags="$run_flags -v `pwd`:/app/alidron-archiver"
    exec_flags="$exec_flags -x"
fi

docker run $run_flags alidron/alidron-archiver-influxdb $exec_flags

if [ $? -eq 0 ]
then
    docker stop -t 0 influx-test
    docker rm influx-test
fi
