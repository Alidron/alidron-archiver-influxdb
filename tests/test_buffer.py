import logging
import os
import pickle
from random import randint

from isac import IsacValue
from isac.tools import green

import alidron_archiver as arch

from test_tools import *

# logging.basicConfig(level=logging.INFO)

def test_buffer_on_db_deleted(config, root_client, clean_db, one_node):
    db = config['archiver-user']['db']
    buffer_path = config['buffer']['path']

    iv = IsacValue(one_node, 'test://test_buffer/test_buffer_on_db_deleted/test', survey_last_value=False, survey_static_tags=False)
    try:
        archiver = arch.InfluxDBArchiver(config)

        base = randint(0, 100)
        iv.value = base
        green.sleep(0.25)

        root_client.drop_database(db)

        iv.value += 10
        iv.value += 10
        green.sleep(0.25)

        assert os.path.exists(buffer_path)
        with open(buffer_path, 'r') as buffer_r:
            assert len(pickle.load(buffer_r)) == 2

        archiver._create_db()
        iv.value += 10
        green.sleep(0.5)

        assert not os.path.exists(buffer_path)
        stored_values = read_data(config, root_client, 'SELECT * FROM /.*/ GROUP BY authority, path ORDER BY time ASC')
        got_values = []
        for uri, points in stored_values.items():
            assert uri == iv.uri
            for point in points:
                got_values.append(point['value_int'])

        expected_values = [i for i in range(base+10, base+40, 10)]
        assert got_values == expected_values

    finally:
        archiver.shutdown()

# TODO: Test it buffers during disconnection ==> How to disconnect the DB??
