FROM alidron/alidron-base-python:2
MAINTAINER Axel Voitier <axel.voitier@gmail.com>

#RUN pip install prospector

RUN pip install influxdb pyaml

#COPY . /usr/src/alidron-isac
ENV PYTHONPATH=/usr/src/alidron-isac

WORKDIR /workspace

