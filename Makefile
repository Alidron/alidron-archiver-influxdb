image_name = alidron/alidron-archiver-influxdb
rpi_image_name = alidron/rpi-alidron-archiver-influxdb
private_rpi_registry = neuron.local:6667

container_name = al-arch-influx

run_alidron_prod_args = --net=alidron -e DB_PORT_8086_TCP_ADDR=192.168.1.5 -e DB_PORT_8086_TCP_PORT=8966 -v $(CURDIR):/workspace -v $(CURDIR)/buffer:/data
run_alidron_prod_args_rpi = --net=alidron -e DB_PORT_8086_TCP_ADDR=192.168.1.5 -e DB_PORT_8086_TCP_PORT=8966 -v $(CURDIR)/config_alidron-prod.yaml:/app/alidron-archiver/config_alidron-prod.yaml -v /var/run/alidron-archiver/buffer:/data
run_alidron_test_args = --net=alidron-test -e DB_PORT_8086_TCP_ADDR=192.168.1.5 -e DB_PORT_8086_TCP_PORT=9966 -v $(CURDIR):/workspace -v $(CURDIR)/buffer-alidron-test:/data
exec_args = python alidron_archiver.py

.PHONY: clean clean-dangling build build-rpi push push-rpi push-rpi-priv pull pull-rpi pull-rpi-priv run-bash run-bash-rpi run run-rpi

clean:
	docker rmi $(image_name) || true

clean-dangling:
	docker rmi `docker images -q -f dangling=true` || true

build: clean-dangling
	docker build --force-rm=true -t $(image_name) .

build-rpi: clean-dangling
	docker build --force-rm=true -t $(rpi_image_name) -f Dockerfile-rpi .

push:
	docker push $(image_name)

push-rpi:
	docker push $(rpi_image_name)

push-rpi-priv:
	docker tag -f $(rpi_image_name) $(private_rpi_registry)/$(rpi_image_name)
	docker push $(private_rpi_registry)/$(rpi_image_name)

pull:
	docker pull $(image_name)

pull-rpi:
	docker pull $(rpi_image_name)

pull-rpi-priv:
	docker pull $(private_rpi_registry)/$(rpi_image_name)
	docker tag $(private_rpi_registry)/$(rpi_image_name) $(rpi_image_name)

run-bash:
	docker run -it --rm --name=$(container_name) $(run_alidron_test_args) $(image_name) bash

run-bash-rpi:
	docker run -it --rm --name=$(container_name) $(run_alidron_test_args) $(rpi_image_name) bash

run-alidron-prod:
	docker run -d --name=$(container_name)-prod $(run_alidron_prod_args) $(image_name) $(exec_args) config_alidron-prod.yaml

run-alidron-test:
	docker run -d --name=$(container_name)-test $(run_alidron_test_args) $(image_name) $(exec_args) config_alidron-test.yaml

run-rpi-alidron-prod:
	docker run -d --name=$(container_name)-prod $(run_alidron_prod_args_rpi) $(rpi_image_name) $(exec_args) config_alidron-prod.yaml

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
