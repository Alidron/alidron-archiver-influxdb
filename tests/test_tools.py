import pytest
from datetime import datetime

from influxdb import InfluxDBClient
from isac import IsacNode

import alidron_archiver as arch

@pytest.fixture(scope='module')
def config():
    return arch._read_config_file('config_template.yaml')

@pytest.fixture(scope='module')
def root_client(config):
    dsn = arch.InfluxDBArchiver.make_DSN(with_db=False, **config['admin-user'])
    client = InfluxDBClient.from_DSN(dsn)

    return client

@pytest.fixture(scope='function')
def clean_db(config, root_client, request):
    db = config['archiver-user']['db']

    def _cleanup():
        if {'name': db} in root_client.get_list_database():
            root_client.drop_database(db)

    _cleanup()
    request.addfinalizer(_cleanup)
    return None

@pytest.fixture(scope='function')
def one_node(request):
    n = IsacNode('test')

    def teardown():
        n.shutdown()

    request.addfinalizer(teardown)
    return n

@pytest.fixture(scope='function')
def two_nodes(request):
    nA = IsacNode('testA')
    nB = IsacNode('testB')

    def teardown():
        nA.shutdown()
        nB.shutdown()

    request.addfinalizer(teardown)
    return nA, nB

def degrade_time(t):
    return datetime(t.year, t.month, t.day, t.hour, t.minute, t.second, (t.microsecond / 1000) * 1000)

def compare_time(t1, t2_dt):
    if not isinstance(t1, datetime):
        try:
            t1_dt = datetime.strptime(t1, '%Y-%m-%dT%H:%M:%S.%fZ')
            t2_dt = degrade_time(t2_dt)
        except ValueError:
            t1_dt = datetime.strptime(t1, '%Y-%m-%dT%H:%M:%SZ')
            t2_dt = datetime(t2_dt.year, t2_dt.month, t2_dt.day, t2_dt.hour, t2_dt.minute, t2_dt.second)

    else:
        t1_dt = t1
        t2_dt = degrade_time(t2_dt)

    assert t1_dt == t2_dt

def read_data(config, root_client, query):
    db = config['archiver-user']['db']
    raw_data = root_client.query(query, database=db)

    data = {}
    for info, points in raw_data.items():
        meas, tags = info
        authority = tags['authority']
        path = tags['path']
        uri = '%s://%s%s' % (meas, authority, path)
        points = list(points)

        data[uri] = points

    return data
