#!/bin/bash

curl -V &> /dev/null
if [ $? -ne 0 ]
then
    apt-get install -y --no-install-recommends curl
fi

if [ `docker ps -f "name=influx-test" | wc -l` -gt 1 ]
then
    docker stop -t 0 influx-test
    docker rm influx-test
fi

docker pull tutum/influxdb:0.9
docker run --rm tutum/influxdb:0.9 cat /etc/influxdb/influxdb.conf > influxdb_test_config.toml
sed -i 's/# engine ="bz1"/engine ="tsm1"/' influxdb_test_config.toml
sed -i 's/auth-enabled = false/auth-enabled = true/' influxdb_test_config.toml
# Can't use a volume to make the config file available because it fails when running the test within a docker container (ie. in the Gitlab CI runner container)...
#docker run -d --name influx-test -p 8083:8083 -p 8086:8086 -v `pwd`/influxdb_test_config.toml:/config/config.toml tutum/influxdb:0.9
docker build --force-rm=true -t alidron/influxdb -f Dockerfile-influxdb-test .
docker run -d --name influx-test -p 8083:8083 -p 8086:8086 alidron/influxdb

DB_IP=`docker inspect influx-test | awk '/"IPAddress"/ {print $2; exit;}' | awk -F'"' '{print $2}'`

RET=1
while [[ RET -ne 0 ]]; do
    echo "=> Waiting for confirmation of InfluxDB service startup ..."
    sleep 0.25
    curl -k "http://$DB_IP:8086/ping" 2> /dev/null
    RET=$?
done

docker exec influx-test influx -host=localhost -port=8086 -execute="CREATE USER root WITH PASSWORD 'root' WITH ALL PRIVILEGES"

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
