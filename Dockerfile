FROM alidron/alidron-isac
MAINTAINER Axel Voitier <axel.voitier@gmail.com>

#RUN pip install prospector

#RUN pip install influxdb pyaml
RUN pip install pyaml
RUN pip install https://github.com/influxdb/influxdb-python/archive/master.zip

#COPY . /usr/src/alidron-isac
#ENV PYTHONPATH=/usr/src/alidron-isac

WORKDIR /workspace
