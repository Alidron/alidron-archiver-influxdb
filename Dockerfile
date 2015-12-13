FROM alidron/alidron-isac
MAINTAINER Axel Voitier <axel.voitier@gmail.com>

WORKDIR /app/alidron-archiver
COPY requirements.txt /app/alidron-archiver/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/alidron-archiver
