import alidron_archiver as arch

from test_tools import *

def test_db_creation(config, root_client, clean_db):
    try:
        archiver = arch.InfluxDBArchiver(config)

        db = config['archiver-user']['db']
        assert {'name': db} in root_client.get_list_database()
        assert {'duration': '0', 'default': True, 'replicaN': 3, 'name': u'default'} in  root_client.get_list_retention_policies(db)
    finally:
        archiver.shutdown()

# TODO: test user creation
