FROM alidron/alidron-isac
MAINTAINER Axel Voitier <axel.voitier@gmail.com>

WORKDIR /workspace
COPY requirements.txt /workspace/
RUN pip install -r requirements.txt
