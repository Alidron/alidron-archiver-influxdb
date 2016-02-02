# Copyright (c) 2015-2016 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

import alidron_archiver as arch

from test_tools import *

# logging.basicConfig(level=logging.ERROR)

def test_db_creation(config, root_client, clean_db):
    archiver = None
    try:
        archiver = arch.InfluxDBArchiver(config)

        db = config['archiver-user']['db']
        assert {'name': db} in root_client.get_list_database()
        assert {'duration': '0', 'default': True, 'replicaN': 3, 'name': u'default'} in  root_client.get_list_retention_policies(db)
    finally:
        if archiver:
            archiver.shutdown()

# TODO: test user creation
