image_name = alidron/alidron-archiver-influxdb

.PHONY: clean clean-dangling build run-bash run

clean:
	docker rmi $(image_name) || true

clean-dangling:
	docker rmi $(docker images -q -f dangling=true) || true

build: clean-dangling
	docker build --force-rm=true -t $(image_name) .

run-bash:
	docker run -it --rm --link influxdb-alidron:db -v /media/nas/Homes/Axel/Development/Alidron/ZWave/axel/alidron-isac:/usr/src/alidron-isac -v $(CURDIR):/workspace $(image_name) bash

run:
	docker run -it --rm $(image_name) python -m isac_cmd hello
