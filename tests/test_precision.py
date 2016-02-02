# Copyright (c) 2015-2016 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import pickle
from datetime import datetime, timedelta
from random import randint

from isac import IsacValue
from isac.tools import green

import alidron_archiver as arch

from test_tools import *

# logging.basicConfig(level=logging.INFO)

def test_precision_by_config_s(config, clean_db, one_node):
    t_start = datetime.now()
    iv = IsacValue(one_node, 'test://test_precision/test_precision_by_config_s/test', survey_last_value=False, survey_static_tags=False)

    try:
        config['config']['default_ts_precision'] = 's'
        archiver = arch.InfluxDBArchiver(config)

        expected_history = []
        def _save_point():
            value, ts, tags = iv.value_ts_tags
            ts = degrade_time(ts, precision='s')
            expected_history.append((value, ts, tags))

        base_ts = datetime.now()
        while base_ts.microsecond > 500000:
            green.sleep(0.1)
            base_ts = datetime.now()

        iv.value_ts = randint(0, 100), base_ts
        iv.value_ts = randint(0, 100), base_ts + timedelta(microseconds=20000)
        _save_point()
        iv.value_ts = randint(0, 100), base_ts + timedelta(seconds=1)
        _save_point()

        green.sleep(0.5)
        t_end = datetime.now() + timedelta(seconds=10)

        data = iv.get_history((t_start, t_end))
        assert data == expected_history

    finally:
        archiver.shutdown()
        config['config']['default_ts_precision'] = arch.DEFAULT_TS_PRECISION

def test_precision_by_config_ms(config, clean_db, one_node):
    t_start = datetime.now()
    iv = IsacValue(one_node, 'test://test_precision/test_precision_by_config_ms/test', survey_last_value=False, survey_static_tags=False)

    try:
        config['config']['default_ts_precision'] = 'ms'
        archiver = arch.InfluxDBArchiver(config)

        expected_history = []
        def _save_point():
            value, ts, tags = iv.value_ts_tags
            ts = degrade_time(ts, precision='ms')
            expected_history.append((value, ts, tags))

        base_ts = datetime.now()
        while base_ts.microsecond > 500:
            green.sleep(0.0001)
            base_ts = datetime.now()

        iv.value_ts = randint(0, 100), base_ts
        iv.value_ts = randint(0, 100), base_ts + timedelta(microseconds=20)
        _save_point()
        iv.value_ts = randint(0, 100), base_ts + timedelta(microseconds=1000)
        _save_point()

        green.sleep(0.5)
        t_end = datetime.now()

        data = iv.get_history((t_start, t_end))
        assert data == expected_history

    finally:
        archiver.shutdown()
        config['config']['default_ts_precision'] = arch.DEFAULT_TS_PRECISION

def test_precision_by_config_u(config, clean_db, one_node):
    t_start = datetime.now()
    iv = IsacValue(one_node, 'test://test_precision/test_precision_by_config_u/test', survey_last_value=False, survey_static_tags=False)

    try:
        config['config']['default_ts_precision'] = 'u'
        archiver = arch.InfluxDBArchiver(config)

        expected_history = []
        def _save_point():
            expected_history.append(iv.value_ts_tags)

        base_ts = datetime.now()
        iv.value_ts = randint(0, 100), base_ts
        _save_point() # When the us happen to be the same, it take the first value, not the last one like for other precisions
        iv.value_ts = randint(0, 100), base_ts
        iv.value_ts = randint(0, 100), base_ts + timedelta(microseconds=1)
        _save_point()

        green.sleep(0.5)
        t_end = datetime.now()

        data = iv.get_history((t_start, t_end))
        assert data == expected_history

    finally:
        archiver.shutdown()
        config['config']['default_ts_precision'] = arch.DEFAULT_TS_PRECISION

def test_precision_by_metadata(config, clean_db, one_node):
    t_start = datetime.now()
    iv_s = IsacValue(one_node, 'test://test_precision/test_precision_by_metadata/test_s', metadata={'ts_precision': 's'}, survey_last_value=False, survey_static_tags=False)
    iv_ms = IsacValue(one_node, 'test://test_precision/test_precision_by_metadata/test_ms', metadata={'ts_precision': 'ms'}, survey_last_value=False, survey_static_tags=False)
    iv_u = IsacValue(one_node, 'test://test_precision/test_precision_by_metadata/test_u', metadata={'ts_precision': 'u'}, survey_last_value=False, survey_static_tags=False)

    try:
        archiver = arch.InfluxDBArchiver(config)

        iv_s_expected_history = []
        iv_ms_expected_history = []
        iv_u_expected_history = []
        def _save_point(iv, expected_history, precision):
            value, ts, tags = iv.value_ts_tags
            if precision in ['s', 'ms']:
                ts = degrade_time(ts, precision)
            expected_history.append((value, ts, tags))

        base_ts = datetime.now()
        while base_ts.microsecond > 500:
            green.sleep(0.0001)
            base_ts = datetime.now()

        # Second
        iv_s.value_ts = randint(0, 100), base_ts
        iv_s.value_ts = randint(0, 100), base_ts + timedelta(microseconds=20000)
        _save_point(iv_s, iv_s_expected_history, 's')
        iv_s.value_ts = randint(0, 100), base_ts + timedelta(seconds=1)
        _save_point(iv_s, iv_s_expected_history, 's')

        # Millisecond
        iv_ms.value_ts = randint(0, 100), base_ts
        iv_ms.value_ts = randint(0, 100), base_ts + timedelta(microseconds=20)
        _save_point(iv_ms, iv_ms_expected_history, 'ms')
        iv_ms.value_ts = randint(0, 100), base_ts + timedelta(microseconds=1000)
        _save_point(iv_ms, iv_ms_expected_history, 'ms')

        # Microsecond
        iv_u.value_ts = randint(0, 100), base_ts
        _save_point(iv_u, iv_u_expected_history, 'u') # When the us happen to be the same, it take the first value, not the last one like for other precisions
        iv_u.value_ts = randint(0, 100), base_ts
        iv_u.value_ts = randint(0, 100), base_ts + timedelta(microseconds=1)
        _save_point(iv_u, iv_u_expected_history, 'u')

        green.sleep(0.5)
        t_end = datetime.now() + timedelta(seconds=10)

        data_s = iv_s.get_history((t_start, t_end))
        assert data_s == iv_s_expected_history

        data_ms = iv_ms.get_history((t_start, t_end))
        assert data_ms == iv_ms_expected_history

        data_u = iv_u.get_history((t_start, t_end))
        assert data_u == iv_u_expected_history

    finally:
        archiver.shutdown()
# test code-default precision
# test config-default precision
# test metadata precision
