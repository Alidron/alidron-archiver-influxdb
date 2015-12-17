image_name = alidron/alidron-archiver-influxdb
rpi_image_name = alidron/rpi-alidron-archiver-influxdb
registry = registry.tinigrifi.org:5000
rpi_registry = neuron.local:6667

container_name = al-arch-influx

run_args = --net=alidron -e DB_PORT_8086_TCP_ADDR=192.168.1.5 -e DB_PORT_8086_TCP_PORT=8086 -v $(CURDIR):/workspace -v $(CURDIR)/buffer:/data # --link influxdb-alidron:db -v /media/nas/Homes/Axel/Development/Alidron/ZWave/axel/alidron-isac:/usr/src/alidron-isac
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
	docker run -it --rm --name=$(container_name) $(run_args) $(image_name) bash

run-bash-rpi:
	docker run -it --rm --name=$(container_name) $(run_args) $(rpi_image_name) bash

run:
	docker run -d --name=$(container_name) $(run_args) $(image_name) $(exec_args)

run-rpi:
	docker run -d --name=$(container_name) $(run_args) $(rpi_image_name) $(exec_args)

stop:
	docker stop -t 0 $(container_name)
	docker rm $(container_name)

logs:
	docker logs -f $(container_name)
