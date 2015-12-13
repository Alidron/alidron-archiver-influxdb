import logging
from random import randint

from isac import IsacNode, IsacValue
from isac.tools import green

import alidron_archiver as arch

from test_tools import *

# logging.basicConfig(level=logging.DEBUG)

def test_detect_all_iv(config, root_client, clean_db, two_nodes):
    nA, nB = two_nodes
    db = config['archiver-user']['db']

    ivs = {}
    def _make_iv(node, uri):
        ivs[uri] = IsacValue(node, uri, static_tags={'nb': uri[-1]}, metadata={'leaf': uri[-4:]}, survey_last_value=False, survey_static_tags=False)
        ivs[uri].value = randint(0, 100)
    _make_iv(nA, 'test://test_init/test_detect_all_iv/iv1A')
    _make_iv(nA, 'test://test_init/test_detect_all_iv/iv2A')
    _make_iv(nB, 'test://test_init/test_detect_all_iv/iv1B')
    _make_iv(nB, 'test://test_init/test_detect_all_iv/iv2B')

    try:
        archiver = arch.InfluxDBArchiver(config)
        green.sleep(0.25)
        stored_values = read_data(config, root_client, 'SELECT * FROM /.*/ GROUP BY authority, path ORDER BY time DESC LIMIT 1')
        checked = []
        checked_metadata = []
        for uri, points in stored_values.items():
            if uri.startswith('metadata'):
                uri = uri.replace('metadata', 'test', 1)
                assert uri in ivs
                assert points[0]['leaf'] == ivs[uri].metadata['leaf']
                assert points[0]['s_nb'] == ivs[uri].static_tags['nb']
                assert points[0]['d_peer_name'] == ivs[uri].isac_node.transport.name()
                assert points[0]['d_peer_uuid'] == str(ivs[uri].isac_node.transport.uuid())
                checked_metadata.append(uri)

            else:
                assert uri in ivs
                assert points[0]['value'] == ivs[uri].value
                compare_time(points[0]['time'], ivs[uri].timestamp)
                assert points[0]['s_nb'] == ivs[uri].static_tags['nb']
                assert points[0]['d_peer_name'] == ivs[uri].isac_node.transport.name()
                assert points[0]['d_peer_uuid'] == str(ivs[uri].isac_node.transport.uuid())
                checked.append(uri)

        assert sorted(checked) == sorted(ivs.keys())
        assert sorted(checked_metadata) == sorted(ivs.keys())
    finally:
        archiver.shutdown()

def test_publish_all_last_values_tags_metadata(config, clean_db, one_node):
    '''
    Full alive->dead->alive cycle:
    - Create a node
    - Create Isac Values
    - Create archiver (and archive current values)
    - Stop node/values
    - Stop archiver
    - Recreate archiver (load from DB the last values + tags + metadata <<< What we want to test)
    - Recreate node
    - Recreate values
    - Finally, assert values, tags and metadata
    '''
    ivs = {}
    def _make_iv(uri):
        iv = IsacValue(one_node, uri, static_tags={'nb': uri[-1]}, metadata={'leaf': uri[-3:]}, survey_last_value=False, survey_static_tags=False)
        iv.value = randint(0, 100)
        ivs[uri] = iv.value, iv.timestamp, iv.tags, iv.static_tags, iv.metadata
    _make_iv('test://test_init/test_publish_all_last_values_tags_metadata/iv1')
    _make_iv('test://test_init/test_publish_all_last_values_tags_metadata/iv2')

    try:
        archiver = arch.InfluxDBArchiver(config)

        one_node.shutdown()
        one_node = None
    finally:
        archiver.shutdown()

    try:
        archiver = arch.InfluxDBArchiver(config)
        try:
            one_node = IsacNode('test2')
            assert one_node.transport.peers() == [archiver.isac_node.transport.uuid()], 'Seems that too much node are still on the network'

            uris = one_node.survey_value_uri('.*')

            assert sorted(uris) == sorted(ivs.keys())

            for uri in ivs.keys():
                iv = IsacValue(one_node, uri)
                iv.survey_metadata()

                assert iv.value == ivs[uri][0]
                compare_time(iv.timestamp, ivs[uri][1])
                # print '>>>>>>', uri, iv.value, iv.timestamp, iv.tags, iv.static_tags
                # TODO: assert iv.tags == ivs[uri][2] # Original peer name/uuid get squashed by IsacValue because we give it an initial value...
                assert iv.static_tags == ivs[uri][3]
                assert iv.metadata == ivs[uri][4]
        finally:
            one_node.shutdown()
    finally:
        archiver.shutdown()
