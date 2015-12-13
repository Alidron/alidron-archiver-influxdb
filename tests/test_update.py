import logging
from random import randint

from isac import IsacValue
from isac.tools import green

import alidron_archiver as arch

from test_tools import *

# logging.basicConfig(level=logging.WARNING)

def test_update_value_tags(config, root_client, clean_db, one_node):
    iv = IsacValue(one_node, 'test://test_update/test_update_value_tags/test', static_tags={'static': 'tag'}, survey_last_value=False, survey_static_tags=False)

    try:
        archiver = arch.InfluxDBArchiver(config)

        iv.value = randint(0, 100)
        green.sleep(0.25)
        stored_values = read_data(config, root_client, 'SELECT * FROM /.*/ GROUP BY authority, path ORDER BY time DESC LIMIT 1')
        for uri, points in stored_values.items():
            assert uri == iv.uri
            assert points[0]['value'] == iv.value
            compare_time(points[0]['time'], iv.timestamp)
            assert points[0]['d_peer_name'] == iv.isac_node.transport.name()
            assert points[0]['d_peer_uuid'] == str(iv.isac_node.transport.uuid())
            assert points[0]['s_static'] == iv.static_tags['static']

        iv.tags['test'] = str(randint(0, 100))
        iv.value = randint(0, 100)
        green.sleep(0.25)
        stored_values = read_data(config, root_client, 'SELECT * FROM /.*/ GROUP BY authority, path ORDER BY time DESC LIMIT 1')
        for uri, points in stored_values.items():
            assert uri == iv.uri
            assert points[0]['value'] == iv.value
            compare_time(points[0]['time'], iv.timestamp)
            assert points[0]['d_test'] == iv.tags['test']
            assert points[0]['d_peer_name'] == iv.isac_node.transport.name()
            assert points[0]['d_peer_uuid'] == str(iv.isac_node.transport.uuid())
            assert points[0]['s_static'] == iv.static_tags['static']


    finally:
        archiver.shutdown()

def test_update_metadata(config, root_client, clean_db, one_node):
    iv = IsacValue(one_node, 'test://test_update/test_update_metadata/test', survey_last_value=False, survey_static_tags=False)

    try:
        archiver = arch.InfluxDBArchiver(config)

        iv.metadata = {'meta': 'data'}
        green.sleep(0.25)
        stored_values = read_data(config, root_client, 'SELECT * FROM /.*/ GROUP BY authority, path ORDER BY time DESC LIMIT 1')
        for uri, points in stored_values.items():
            uri = uri.replace('metadata', points[0]['scheme'], 1)
            assert uri == iv.uri
            assert points[0]['meta'] == iv.metadata['meta']

    finally:
        archiver.shutdown()

def test_update_new_value(config, root_client, clean_db, one_node):
    try:
        archiver = arch.InfluxDBArchiver(config)

        iv = IsacValue(
            one_node, 'test://test_update/test_update_new_value/test', randint(0, 100),
            static_tags={'static': 'tags'}, dynamic_tags={'test': str(randint(0, 100))},
            metadata={'meta': 'data'}, survey_last_value=False, survey_static_tags=False
        )

        green.sleep(0.5)
        stored_values = read_data(config, root_client, 'SELECT * FROM /.*/ GROUP BY authority, path ORDER BY time DESC LIMIT 1')
        checked = False
        checked_metadata = False
        for uri, points in stored_values.items():
            if uri.startswith('metadata'):
                uri = uri.replace('metadata', 'test', 1)
                assert uri == iv.uri
                assert points[0]['meta'] == iv.metadata['meta']
                assert points[0]['s_static'] == iv.static_tags['static']
                assert points[0]['d_peer_name'] == iv.isac_node.transport.name()
                assert points[0]['d_peer_uuid'] == str(iv.isac_node.transport.uuid())
                checked_metadata = True

            else:
                assert uri == iv.uri
                assert points[0]['value'] == iv.value
                compare_time(points[0]['time'], iv.timestamp)
                assert points[0]['s_static'] == iv.static_tags['static']
                assert points[0]['d_peer_name'] == iv.isac_node.transport.name()
                assert points[0]['d_peer_uuid'] == str(iv.isac_node.transport.uuid())
                assert points[0]['d_test'] == iv.tags['test']
                checked = True

        assert checked, 'Could not read record for value update'
        assert checked_metadata, 'Could not read record for metadata update'

    finally:
        archiver.shutdown()
