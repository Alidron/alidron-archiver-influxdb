image_name = alidron/alidron-archiver-influxdb
rpi_image_name = alidron/rpi-alidron-archiver-influxdb
registry = registry.tinigrifi.org:5000
rpi_registry = neuron.local:6667

container_name = al-arch-influx

run_alidron_prod_args = --net=alidron -e DB_PORT_8086_TCP_ADDR=192.168.1.5 -e DB_PORT_8086_TCP_PORT=8966 -v $(CURDIR):/workspace -v $(CURDIR)/buffer:/data # --link influxdb-alidron:db -v /media/nas/Homes/Axel/Development/Alidron/ZWave/axel/alidron-isac:/usr/src/alidron-isac
run_alidron_test_args = --net=alidron-test -e DB_PORT_8086_TCP_ADDR=192.168.1.5 -e DB_PORT_8086_TCP_PORT=9966 -v $(CURDIR):/workspace -v $(CURDIR)/buffer-alidron-test:/data
exec_args = python alidron_archiver.py

.PHONY: clean clean-dangling build build-rpi push push-rpi pull pull-rpi run-bash run-bash-rpi run run-rpi

clean:
	docker rmi $(image_name) || true

clean-dangling:
	docker rmi `docker images -q -f dangling=true` || true

build: clean-dangling
	docker build --force-rm=true -t $(image_name) .

build-rpi: clean-dangling
	docker build --force-rm=true -t $(rpi_image_name) -f Dockerfile-rpi .

push:
	docker tag -f $(image_name) $(registry)/$(image_name)
	docker push $(registry)/$(image_name)

push-rpi:
	docker tag -f $(rpi_image_name) $(rpi_registry)/$(rpi_image_name)
	docker push $(rpi_registry)/$(rpi_image_name)

pull:
	docker pull $(registry)/$(image_name)
	docker tag $(registry)/$(image_name) $(image_name)

pull-rpi:
	docker pull $(rpi_registry)/$(rpi_image_name)
	docker tag $(rpi_registry)/$(rpi_image_name) $(rpi_image_name)

run-bash:
	docker run -it --rm --name=$(container_name) $(run_alidron_test_args) $(image_name) bash

run-bash-rpi:
	docker run -it --rm --name=$(container_name) $(run_alidron_test_args) $(rpi_image_name) bash

run-alidron-prod:
	docker run -d --name=$(container_name)-prod $(run_alidron_prod_args) $(image_name) $(exec_args) config_alidron-prod.yaml

run-alidron-test:
	docker run -d --name=$(container_name)-test $(run_alidron_test_args) $(image_name) $(exec_args) config_alidron-test.yaml

run-rpi-alidron-prod:
	docker run -d --name=$(container_name) $(run_alidron_prod_args) $(rpi_image_name) $(exec_args) config_alidron-prod.yaml

stop-prod:
	docker stop -t 0 $(container_name)-prod
	docker rm $(container_name)-prod

logs-prod:
	docker logs -f $(container_name)-prod

stop-test:
	docker stop -t 0 $(container_name)-test
	docker rm $(container_name)-test

logs-test:
	docker logs -f $(container_name)-test

