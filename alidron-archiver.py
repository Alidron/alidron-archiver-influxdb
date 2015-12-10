import json
import logging
import os
import pickle
import re
import signal
import sys
import time
import yaml
from datetime import datetime
from functools import partial
from math import floor
from pprint import pprint as pp, pformat as pf
from requests.exceptions import ConnectionError
from uritools import urisplit, uricompose

#from influxdb.influxdb08 import InfluxDBClient, SeriesHelper
#from influxdb.influxdb08.client import InfluxDBClientError
import influxdb
from influxdb import InfluxDBClient
from influxdb.client import InfluxDBClientError

from isac import IsacNode, ArchivedValue
from isac.tools import Observable, green

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)

logger.info('Starting')

print 'Version:', influxdb.__version__

class InfluxDBArchivedValue(ArchivedValue):

    def __init__(self, *args, **kwargs):
        self.influxdb_client = kwargs.pop('influxdb_client')
        super(self.__class__, self).__init__(*args, **kwargs)

    def get_history_impl(self, time_period):
        logger.info('Got a call for get_history_impl for value %s with a time period of %s', self.uri, time_period)

        begin, end = time_period
        if begin and end:
            time_filter = 'AND time > %du AND time < %du' % (begin*1e6, end*1e6)
        elif begin and not end:
            time_filter = 'AND time > %du' % begin*1e6
        elif not begin and end:
            time_filter = 'AND time < %du' % end*1e6
        else:
            time_filter = ''

        uri = urisplit(self.uri)
        query = "SELECT * FROM %s WHERE authority='%s' AND path='%s' %s" % (uri.scheme, uri.authority, uri.path, time_filter)
        logger.info('Doing query: %s', query)
        try:
            raw_data = self.influxdb_client.query(query)
        except InfluxDBClientError as ex:
            if ex.code != 400:
                raise
            raw_data = []

        logger.debug('Raw data: %s', pf(list(raw_data.items()[0][1])))
        data = []
        if raw_data:
            for point in raw_data.items()[0][1]:
                try:
                    ts = datetime.strptime(point['time'], '%Y-%m-%dT%H:%M:%S.%fZ')
                except ValueError:
                    ts = datetime.strptime(point['time'], '%Y-%m-%dT%H:%M:%SZ')
                ts_float = time.mktime(ts.timetuple()) + (ts.microsecond / 1000000.0)

                dynamic_tags = {}
                for k, v in point.items():
                    if k.startswith('d_'):
                        dynamic_tags[k[2:]] = v

                data.append((point['value'], ts_float, dynamic_tags))

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
        green.signal(signal.SIGTERM, partial(self._sigterm_handler))
        green.signal(signal.SIGINT, partial(self._sigterm_handler))

        self.signals = {}

        raw_data = self._client.query('SELECT * FROM /.*/ GROUP BY authority, path ORDER BY time DESC LIMIT 1')
        logger.debug('Raw data: %s', pf(raw_data.items()))
        metadata = {}

        def _make_uri(meas, tags):
            uri_str = uricompose(scheme=meas, authority=tags['authority'], path=tags['path'])
            return uri_str, urisplit(uri_str)

        for meas_tags, fields in raw_data.items():
            uri_str, uri = _make_uri(*meas_tags)
            if uri.scheme == 'metadata':
                metadata[uri_str] = fields.next()

        for meas_tags, data in raw_data.items():
            uri_str, uri = _make_uri(*meas_tags)
            if uri.scheme == 'metadata':
                continue

            last_point = data.next()

            try:
                ts = datetime.strptime(last_point['time'], '%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError:
                ts = datetime.strptime(last_point['time'], '%Y-%m-%dT%H:%M:%SZ')

            static_tags = {}
            dynamic_tags = {}
            for k, v in last_point.items():
                if k.startswith('s_'):
                    static_tags[k[2:]] = v
                elif k.startswith('d_'):
                    dynamic_tags[k[2:]] = v

            logger.debug('For URI %s: %s, %s', uri_str, ts, pf(last_point))

            self.signals[uri_str] = InfluxDBArchivedValue(
                self.isac_node, uri_str,
                initial_value=(last_point['value'], ts),
                static_tags=static_tags, dynamic_tags=dynamic_tags,
                observers=Observable([self._notify]), influxdb_client=self._client,
                metadata=metadata.get(uri_str, None),
                survey_last_value=False,
                survey_static_tags=False
            )
            self.signals[uri_str].metadata_observers += self._notify_metadata
            self.signals[uri_str].survey_metadata()

        self.isac_node.register_isac_value_entering(self._new_signal)
        signal_uris = self.isac_node.survey_value_uri('.*')
        map(partial(self._new_signal, ''), signal_uris)

    def _new_signal(self, peer_name, signal_uri):
        signal_uri = signal_uri.encode()
        if signal_uri not in self.signals:
            logger.info('Signal %s will be archived', signal_uri)
            self.signals[signal_uri] = InfluxDBArchivedValue(self.isac_node, signal_uri, observers=Observable([self._notify]), influxdb_client=self._client)
            self.signals[signal_uri].metadata_observers += self._notify_metadata
            self.signals[signal_uri].survey_metadata()
            logger.debug('>>>>> static_tags %s: %s', signal_uri, self.signals[signal_uri].static_tags)

    @staticmethod
    def _prefix_keys(d, prefix):
        return {prefix+k: v for k, v in d.items()}

    def _notify(self, iv, value, ts, dynamic_tags):
        # We are already in a green thread here
        uri = urisplit(iv.uri)
        data = []

        def _make_data(value, ts, dynamic_tags):
            tags = self._prefix_keys(iv.static_tags, 's_')
            tags.update(self._prefix_keys(dynamic_tags, 'd_'))
            tags['authority'] = uri.authority
            tags['path'] = uri.path

            return {
                'measurement': uri.scheme,
                'time': ts,
                'fields': {'value': value},
                'tags': tags,
            }

        # Handle smoothing
        default_smoothing = bool(config.get('config', {}).get('default_smoothing', False))
        smoothing = iv.metadata.get('smoothing', default_smoothing) if iv.metadata else default_smoothing
        logger.debug('Smoothing: %s', smoothing)
        if smoothing:
            prev_value, prev_ts, prev_tags = getattr(iv, '_arch_prev_update', (None, datetime.fromtimestamp(0), {}))
            in_smoothing = getattr(iv, '_arch_in_smoothing', False)

            iv._arch_prev_update = (value, ts, dynamic_tags)
            if (prev_value == value) and (dynamic_tags == prev_tags):
                logger.debug('Smoothing detected same value and tags, not sending to DB')
                iv._arch_in_smoothing = True
                return
            elif in_smoothing:
                # Flush last same value to provide an end time for the smoothed out period
                logger.debug('Smoothing detected a different value than the one smoothed before. Flushing last same value')
                data.append(_make_data(prev_value, prev_ts, prev_tags))
                iv._arch_in_smoothing = False
            else:
                logger.debug('Smoothing detected normal value change: %s, %s, %s / %s, %s, %s', prev_value, prev_ts, prev_tags, value, ts, dynamic_tags)

        data.append(_make_data(value, ts, dynamic_tags))

        precision = config.get('config', {}).get('default_precision', 'ms')
        if iv.metadata and 'ts_precision' in iv.metadata:
            precision = iv.metadata['ts_precision']

        logger.info('Writing for %s: %s', uri, data)

        self._write_data(data, precision)

    def _notify_metadata(self, iv, metadata):
        # We are already in a green thread here
        if not isinstance(metadata, dict):
            metadata = {'metadata': metadata}

        uri = urisplit(iv.uri)

        tags = self._prefix_keys(iv.static_tags, 's_')
        tags.update(self._prefix_keys(iv.tags, 'd_'))
        tags['authority'] = uri.authority
        tags['path'] = uri.path

        data = [{
            'measurement': uri.scheme,
            'fields': metadata,
            'tags': tags
        }]
        logger.info('Writing metadata for %s: %s', uri, metadata)

        self._write_data(data)

    def _write_data(self, data, precision='ms'):
        previous_data = []
        if os.path.exists(config['buffer']['path']):
            with open(config['buffer']['path'], 'r') as buffer_r:
                previous_data += pickle.load(buffer_r)
            logger.info('Read %d records from buffer', len(previous_data))

        new_data = previous_data + data
        try:
            self._client.write_points(new_data, time_precision=precision)
        except (ConnectionError, InfluxDBClientError) as ex:
            logger.error('Failed to write to DB, flushing to buffer: %s', ex)

            with open(config['buffer']['path'], 'w') as buffer_w:
                pickle.dump(previous_data + data, buffer_w, -1)

            logger.info('%d records in buffer', len(new_data))

            return

        logger.info('Flushed %d records to DB', len(new_data))

        # Write succeeded, clear buffer
        if os.path.exists(config['buffer']['path']):
            os.remove(config['buffer']['path'])

    def _sigterm_handler(self):
        logger.info('Received SIGTERM signal, exiting')
        self.isac_node.shutdown()
        logger.info('Exiting')
        sys.exit(0)

    def serve_forever(self):
        try:
            while True:
                green.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info('Stopping')
            self.isac_node.shutdown()


def _config_parse_env(config):
    if isinstance(config, list):
        map(_config_parse_env, config)
    elif isinstance(config, dict):
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
