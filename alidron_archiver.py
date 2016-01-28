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

from influxdb import InfluxDBClient
from influxdb.client import InfluxDBClientError

from isac import IsacNode, ArchivedValue
from isac.tools import Observable, green

logger = logging.getLogger(__name__)

DEFAULT_TS_PRECISION = 'ms'
DEFAULT_SMOOTHING = False

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

                data.append((InfluxDBArchiver._type_from_db_to_py(point), ts_float, dynamic_tags))

        return data


class InfluxDBArchiver(object):

    @staticmethod
    def make_DSN(with_db=True, **kwargs):
        if with_db:
            return '{scheme}://{username}@{hostname}:{port}/{db}'.format(**kwargs)
        else:
            return '{scheme}://{username}@{hostname}:{port}'.format(**kwargs)

    _type_list_py_db = [
        (bool, 'boolean'),
        (str, 'string'),
        (unicode, 'string'),
        (int, 'int'),
        (float, 'real'),
    ]
    _types_from_py_to_db = dict(_type_list_py_db)
    _types_from_db_to_py = dict([(db, py) for py, db in _type_list_py_db])

    def __init__(self, config):
        logger.info('Starting')
        self.config = config

        buffer_path = self.config['buffer']['path']
        if not os.path.exists(os.path.dirname(buffer_path)):
            os.makedirs(os.path.dirname(buffer_path))

        dsn = InfluxDBArchiver.make_DSN(**self.config['archiver-user'])
        for i in range(2):
            self._client = InfluxDBClient.from_DSN(dsn, password=self.config['archiver-user']['password'])
            try:
                self._client.query('SHOW MEASUREMENTS')
                break
            except InfluxDBClientError as ex:
                if ex.code == 401:
                    logger.error(ex)
                    logger.warning('Could not connect as user %s, trying as root to setup the DB', self.config['archiver-user']['username'])
                    self._create_user()
                elif ex.message.startswith('database not found'):
                    logger.warning('Could not find database %s, creating it', self.config['archiver-user']['db'])
                    self._create_db()
                else:
                    raise
        logger.info('Connected to DB with %s', dsn)

        self.isac_node = IsacNode('alidron-archiver-influxdb')
        green.signal(signal.SIGTERM, partial(self._sigterm_handler))
        green.signal(signal.SIGINT, partial(self._sigterm_handler))

        self.signals = {}

        query = 'SELECT * FROM /.*/ GROUP BY authority, path ORDER BY time DESC LIMIT 1'
        logger.debug('Doing query: %s', query)
        raw_data = self._client.query(query)
        logger.debug('Raw data: %s', pf(raw_data.items()))
        metadata = {}

        def _make_uri(meas, tags):
            uri_str = uricompose(scheme=meas, authority=tags['authority'], path=tags['path'])
            return uri_str, urisplit(uri_str)

        for meas_tags, fields in raw_data.items():
            uri_str, uri = _make_uri(*meas_tags)
            if uri.scheme == 'metadata':
                raw_metadata = fields.next()
                uri_str = uri_str.replace('metadata', raw_metadata['scheme'], 1)
                metadata[uri_str] = {}
                for key, value in raw_metadata.items():
                    if key.startswith('d_') or key.startswith('s_') or key in ['time', 'scheme']:
                        continue
                    if (key.startswith('value')) and (value is None):
                        continue

                    if key.startswith('json_'):
                        if value is None:
                            metadata[uri_str][key[len('json_'):]] = None
                        else:
                            try:
                                metadata[uri_str][key[len('json_'):]] = json.loads(str(value))
                            except ValueError:
                                logger.error('Wrong JSON for %s at key %s: %s', uri_str, key, str(value))
                                continue
                    else:
                        metadata[uri_str][key] = value

                logger.debug('Read metadata for %s: %s', uri_str, metadata[uri_str])

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
            logger.debug('Decoded tags: %s, %s', static_tags, dynamic_tags)

            self.signals[uri_str] = InfluxDBArchivedValue(
                self.isac_node, uri_str,
                initial_value=(self._type_from_db_to_py(last_point), ts),
                static_tags=static_tags, dynamic_tags=dynamic_tags,
                observers=Observable([self._notify]),
                metadata=metadata.get(uri_str, None),
                survey_last_value=False,
                survey_static_tags=False,
                influxdb_client=self._client,
            )
            self.signals[uri_str].metadata_observers += self._notify_metadata
            green.spawn(self.signals[uri_str].survey_metadata)

            logger.warning('Discovered %s', uri_str)

        logger.warning('Done loading existing signals')

        self.isac_node.register_isac_value_entering(self._new_signal)
        signal_uris = self.isac_node.survey_value_uri('.*')
        map(partial(self._new_signal, ''), signal_uris)

    def _create_user(self):
        dsn = InfluxDBArchiver.make_DSN(with_db=False, **self.config['admin-user'])
        root_client = InfluxDBClient.from_DSN(dsn, password=self.config['admin-user']['password'])

        root_client.create_user(self.config['archiver-user']['username'], self.config['archiver-user']['password'])
        root_client.grant_privilege('all', self.config['archiver-user']['db'], self.config['archiver-user']['username'])

        # dsn = InfluxDBArchiver.make_DSN(with_db=False, **self.config['archiver-user'])
        # self._client = InfluxDBClient.from_DSN(dsn, password=self.config['archiver-user']['password'])

    def _create_db(self):
        dsn = InfluxDBArchiver.make_DSN(with_db=False, **self.config['admin-user'])
        root_client = InfluxDBClient.from_DSN(dsn, password=self.config['admin-user']['password'])

        db = self.config['archiver-user']['db']
        root_client.create_database(db)
        root_client.alter_retention_policy('default', db, replication='3')

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

    @staticmethod
    def _type_from_py_to_db(value):
        if type(value) in InfluxDBArchiver._types_from_py_to_db.keys():
            field_name = 'value_' + InfluxDBArchiver._types_from_py_to_db[type(value)]
        else:
            field_name = 'value_json'
            value = json.dumps(value)

        return field_name, value

    @staticmethod
    def _type_from_db_to_py(fields):
        for field_name, value in fields.items():
            if not field_name.startswith('value_'):
                continue
            elif value is None:
                continue
            else:
                if field_name == 'value_json':
                    return json.loads(value)
                else:
                    return InfluxDBArchiver._types_from_db_to_py[field_name[len('value_'):]](value)

    def _notify(self, iv, value, ts, dynamic_tags):
        # We are already in a green thread here
        uri = urisplit(iv.uri)
        data = []

        def _make_data(value, ts, dynamic_tags):
            tags = self._prefix_keys(iv.static_tags, 's_')
            tags.update(self._prefix_keys(dynamic_tags, 'd_'))
            tags['authority'] = uri.authority
            tags['path'] = uri.path

            field_name, value = self._type_from_py_to_db(value)

            return {
                'measurement': uri.scheme,
                'time': ts,
                'fields': {field_name: value},
                'tags': tags,
            }

        # Handle smoothing
        default_smoothing = self.config.get('config', {}).get('default_smoothing', DEFAULT_SMOOTHING)
        smoothing = iv.metadata.get('smoothing', default_smoothing) if iv.metadata else default_smoothing
        logger.debug('Smoothing: %s', smoothing)
        if bool(smoothing):
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

        precision = self.config.get('config', {}).get('default_ts_precision', DEFAULT_TS_PRECISION)
        if iv.metadata and 'ts_precision' in iv.metadata:
            precision = iv.metadata['ts_precision']

        logger.info('Writing for %s: %s', uri, data)

        self._write_data(data, precision)

    def _notify_metadata(self, iv, metadata, source_peer):
        # We are already in a green thread here
        if not isinstance(metadata, dict):
            metadata = {'metadata': metadata}

        uri = urisplit(iv.uri)

        tags = self._prefix_keys(iv.static_tags, 's_')
        tags.update(self._prefix_keys(source_peer, 'd_'))
        tags['authority'] = uri.authority
        tags['path'] = uri.path
        tags['scheme'] = uri.scheme

        metadata_to_write = {}
        for k, v in metadata.items():
            if type(v) not in InfluxDBArchiver._types_from_py_to_db.keys():
                metadata_to_write['json_' + k] = json.dumps(v)
            else:
                metadata_to_write[k] = v

        data = [{
            'measurement': 'metadata',
            'fields': metadata_to_write,
            'tags': tags
        }]
        logger.info('Writing metadata for %s: %s', uri, metadata)

        self._write_data(data)

    def _write_data(self, data, precision='ms'):
        previous_data = []
        if os.path.exists(self.config['buffer']['path']):
            with open(self.config['buffer']['path'], 'r') as buffer_r:
                previous_data += pickle.load(buffer_r)
            logger.info('Read %d records from buffer', len(previous_data))

        new_data = previous_data + data
        try:
            self._client.write_points(new_data, time_precision=precision)
        except (ConnectionError, InfluxDBClientError) as ex:
            logger.error('Failed to write to DB, flushing to buffer: %s', ex)

            with open(self.config['buffer']['path'], 'w') as buffer_w:
                pickle.dump(previous_data + data, buffer_w, -1)

            logger.info('%d records in buffer', len(new_data))

            return

        logger.info('Flushed %d records to DB', len(new_data))

        # Write succeeded, clear buffer
        if os.path.exists(self.config['buffer']['path']):
            os.remove(self.config['buffer']['path'])

    def shutdown(self):
        logger.info('Stopping')
        self._running = False
        self.isac_node.shutdown()

    def _sigterm_handler(self):
        logger.info('Received SIGTERM signal, exiting')
        self.shutdown()
        logger.info('Exiting')
        sys.exit(0)

    def serve_forever(self):
        self._running = True
        try:
            while self._running:
                green.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.shutdown()


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

def _read_config_file(other_path=None):
    if other_path:
        config_path = other_path
    else:
        try:
            config_path = sys.argv[1]
        except IndexError:
            config_path = 'config.yaml'

    with open(config_path, 'r') as config_file:
        config = yaml.load(config_file)

    _config_parse_env(config)
    return config

if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)

    config = _read_config_file()

    client = InfluxDBArchiver(config)
    client.serve_forever()
