# Copyright (c) 2015-2016 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

FROM alidron/alidron-isac
MAINTAINER Axel Voitier <axel.voitier@gmail.com>

WORKDIR /app/alidron-archiver
COPY requirements.txt /app/alidron-archiver/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/alidron-archiver
