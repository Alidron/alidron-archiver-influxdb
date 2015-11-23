import json
import logging
import os
import re
import signal
import sys
import time
import yaml
from datetime import datetime
from functools import partial
from math import floor
from pprint import pprint as pp

#from influxdb.influxdb08 import InfluxDBClient, SeriesHelper
#from influxdb.influxdb08.client import InfluxDBClientError
import influxdb
from influxdb import InfluxDBClient
from influxdb.client import InfluxDBClientError

import gevent

from isac import IsacNode, ArchivedValue
from isac.tools import Observable

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

logger.info('Starting')

print 'Version:', influxdb.__version__

class InfluxDBArchivedValue(ArchivedValue):

    def __init__(self, *args, **kwargs):
        self.influxdb_client = kwargs.pop('influxdb_client')
        super(self.__class__, self).__init__(*args, **kwargs)

    def get_history_impl(self, time_period):
        logger.info('Got a call for get_history_impl for value %s with a time period of %s', self.name, time_period)

        begin, end = time_period
        if begin and end:
            time_filter = 'WHERE time > %fs AND time < %fs' % (begin, end)
        elif begin and not end:
            time_filter = 'WHERE time > %fs' % begin
        elif not begin and end:
            time_filter = 'WHERE time < %fs' % end
        else:
            time_filter = ''

        query = 'SELECT * FROM %s %s' % (self.name, time_filter)
        logger.info('Doing query: %s', query)
        try:
            raw_data = self.influxdb_client.query(query, time_precision='ms')
        except InfluxDBClientError as ex:
            if ex.code != 400:
                raise
            raw_data = []

        data = []
        if raw_data:
            for point in raw_data[0]['points']:
                ts_float = (point[0] * 1e-3) + (point[1] * 1e-9)
                data.append((point[2], ts_float))

        return data


class InfluxDBArchiver(object):

    @staticmethod
    def make_DSN(with_db=True, **kwargs):
        if with_db:
            return '{scheme}://{username}:{password}@{hostname}:{port}/{db}'.format(**kwargs)
        else:
            return '{scheme}://{username}:{password}@{hostname}:{port}'.format(**kwargs)

    def __init__(self, config):
        dsn = InfluxDBArchiver.make_DSN(**config['archiver-user'])
        # self._client = InfluxDBClient.from_DSN(dsn, password=config['archiver-user']['password'])
        self._client = InfluxDBClient.from_DSN(dsn)
        try:
            self._client.query('show measurements')
        except InfluxDBClientError as ex:
            if ex.code != 401:
                raise

            logger.info('Could not connect as user %s, trying as root to setup the DB', config['archiver-user']['username'])

            dsn = InfluxDBArchiver.make_DSN(with_db=False, **config['admin-user'])
            client = InfluxDBClient.from_DSN(dsn, password=config['admin-user']['password'])

            db_list = client.get_list_database()
            if config['archiver-user']['db'] not in map(lambda db: db['name'], db_list):
                logger.info('Creating database %s', config['archiver-user']['db'])
                client.create_database(config['archiver-user']['db'])

            # Can't do much from here with the 0.8 api
            # But from 0.9 we can use get_list_users, switch_database and create_user

            dsn = InfluxDBArchiver.make_DSN(**config['archiver-user'])
            self._client = InfluxDBClient.from_DSN(dsn, password=config['archiver-user']['password'])


        self.isac_node = IsacNode('alidron-archiver-influxdb')
        gevent.signal(signal.SIGTERM, partial(self._sigterm_handler))
        gevent.signal(signal.SIGINT, partial(self._sigterm_handler))

        self.signals = {}

        raw_data = self._client.query('SELECT * FROM /.*/ LIMIT 1')
        metadata = {}
        for meas_tags, fields in raw_data.items():
            value_name = meas_tags[0].encode()
            if value_name.startswith('metadata.'):
                metadata[value_name[9:]] = fields.next()

        for meas_tags, fields in raw_data.items():
            value_name = meas_tags[0].encode()
            if value_name.startswith('metadata.'):
                continue

            print '##############', value_name, type(metadata.get(value_name, None)), metadata.get(value_name, None)
            last_point = fields.next()
            
            try:
                ts = datetime.strptime(last_point['time'], '%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError:
                ts = datetime.strptime(last_point['time'], '%Y-%m-%dT%H:%M:%SZ')

            self.signals[value_name] = InfluxDBArchivedValue(
                self.isac_node, value_name,
                initial_value=(last_point['value'], ts),
                observers=Observable([self._notify]), influxdb_client=self._client,
                metadata=metadata.get(value_name, None)
            )
            self.signals[value_name].metadata_observers += self._notify_metadata
            self.signals[value_name].survey_metadata()

        self.isac_node.register_isac_value_entering(self._new_signal)
        signal_names = self.isac_node.survey_value_name('.*')
        map(partial(self._new_signal, ''), signal_names)

    def _new_signal(self, peer_name, signal_name):
        signal_name = signal_name.encode()
        if signal_name not in self.signals:
            logger.info('Signal %s will be archived', signal_name)
            self.signals[signal_name] = InfluxDBArchivedValue(self.isac_node, signal_name, observers=Observable([self._notify]), influxdb_client=self._client)
            self.signals[signal_name].metadata_observers += self._notify_metadata
            self.signals[signal_name].survey_metadata()


    def _notify(self, name, value, ts):
        ts_ = int((time.mktime(ts.timetuple()) * 1000) + floor(ts.microsecond / 1000))
        ns = (ts.microsecond % 1000) * 1000 # Give the nanosecond resolution
        if ns:
            data = [{
                'measurement': name,
                'time': ts,
                'fields': {'value': value},
                'tags': {'nanosecond': ns},
                #'columns': ['time', 'sequence_number', 'value'],
                #'points': [[ts_, seq_n, value]],
            }]
        else:
            data = [{
                'measurement': name,
                'time': ts,
                'fields': {'value': value},
            }]
        logger.info('Writing for %s: %s, %s, %s', name, ts_, ns, data)
        self._client.write_points(data, time_precision='ms')

    def _notify_metadata(self, name, metadata):
        if not isinstance(metadata, dict):
            metadata = {'metadata': metadata}
        data = [{
            'measurement': 'metadata.' + name,
            'fields': metadata
            #'columns': ['metadata'],
            #'points': [[json.dumps(metadata)]],
        }]
        logger.info('Writing metadata for %s: %s', name, metadata)
        self._client.write_points(data)

    def _sigterm_handler(self):
        logger.info('Received SIGTERM signal, exiting')
        self.isac_node.shutdown()
        logger.info('Exiting')
        sys.exit(0)

    def serve_forever(self):
        try:
            while True:
                gevent.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info('Stopping')
            self.isac_node.shutdown()


def _config_parse_env(config):
    if isinstance(config, list):
        map(_config_parse_env, config)
    else:
        for k,v in config.items():
            if isinstance(v, str) or isinstance(v, unicode):
                m = re.match("env\['(.*)'\]", v)
                if m:
                    config[k] = os.environ[m.group(1)]
            else:
                _config_parse_env(v)


if __name__ == '__main__':
    with open('config.yaml', 'r') as config_file:
        config = yaml.load(config_file)

    _config_parse_env(config)

    client = InfluxDBArchiver(config)
    client.serve_forever()
