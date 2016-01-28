# Copyright 2015-2016 - Alidron's authors
#
# This file is part of Alidron.
#
# Alidron is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Alidron is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Alidron.  If not, see <http://www.gnu.org/licenses/>.

FROM alidron/alidron-isac
MAINTAINER Axel Voitier <axel.voitier@gmail.com>

WORKDIR /app/alidron-archiver
COPY requirements.txt /app/alidron-archiver/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/alidron-archiver
