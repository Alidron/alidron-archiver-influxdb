import logging
import os
import pickle
from datetime import datetime
from random import randint

from isac import IsacValue
from isac.tools import green

import alidron_archiver as arch

from test_tools import *

# logging.basicConfig(level=logging.INFO)

def test_smoothing_by_config(config, clean_db, one_node):
    t_start = datetime.now()
    iv = IsacValue(one_node, 'test://test_smoothing/test_smoothing_by_config/test', survey_last_value=False, survey_static_tags=False)

    try:
        config['config']['default_smoothing'] = True
        archiver = arch.InfluxDBArchiver(config)

        expected_history = []
        def _save_point():
            value, ts, tags = iv.value_ts_tags
            ts = degrade_time(ts)
            expected_history.append((value, ts, tags))

        base = randint(0, 100)
        iv.value = base
        _save_point()
        iv.value += 10
        _save_point()
        iv.value = iv.value
        iv.value = iv.value
        iv.value = iv.value
        iv.value = iv.value
        _save_point()
        iv.value += 10
        _save_point()

        green.sleep(0.5)
        t_end = datetime.now()

        data = iv.get_history((t_start, t_end))
        assert data == expected_history

    finally:
        archiver.shutdown()
        config['config']['default_smoothing'] = arch.DEFAULT_SMOOTHING

def test_smoothing_by_metadata(config, clean_db, one_node):
    t_start = datetime.now()
    ivS = IsacValue(one_node, 'test://test_smoothing/test_smoothing_by_metadata/test_smoothing', metadata={'smoothing': True}, survey_last_value=False, survey_static_tags=False)
    ivNS = IsacValue(one_node, 'test://test_smoothing/test_smoothing_by_metadata/test_no_smoothing', survey_last_value=False, survey_static_tags=False)
    ivSF = IsacValue(one_node, 'test://test_smoothing/test_smoothing_by_metadata/test_smoothing_false', metadata={'smoothing': False}, survey_last_value=False, survey_static_tags=False)

    try:
        archiver = arch.InfluxDBArchiver(config)


        ivS_expected_history = []
        ivNS_expected_history = []
        ivSF_expected_history = []
        def _save_point(iv, record):
            value, ts, tags = iv.value_ts_tags
            ts = degrade_time(ts)
            record.append((value, ts, tags))

        def _save_all_points():
            _save_point(ivS, ivS_expected_history)
            _save_point(ivNS, ivNS_expected_history)
            _save_point(ivSF, ivSF_expected_history)

        def _save_not_smoothed_points():
            _save_point(ivNS, ivNS_expected_history)
            _save_point(ivSF, ivSF_expected_history)


        base = randint(0, 100)
        ivS.value = ivNS.value = ivSF.value = base
        _save_all_points()
        ivS.value = ivNS.value = ivSF.value = ivS.value + 10
        _save_all_points()
        ivS.value = ivNS.value = ivSF.value = ivS.value
        _save_not_smoothed_points()
        ivS.value = ivNS.value = ivSF.value = ivS.value
        _save_not_smoothed_points()
        ivS.value = ivNS.value = ivSF.value = ivS.value
        _save_not_smoothed_points()
        ivS.value = ivNS.value = ivSF.value = ivS.value
        _save_all_points()
        ivS.value = ivNS.value = ivSF.value = ivS.value + 10
        _save_all_points()

        green.sleep(0.5)
        t_end = datetime.now()

        data_ivS = ivS.get_history((t_start, t_end))
        assert data_ivS == ivS_expected_history

        data_ivNS = ivNS.get_history((t_start, t_end))
        assert data_ivNS == ivNS_expected_history

        data_ivSF = ivSF.get_history((t_start, t_end))
        assert data_ivSF == ivSF_expected_history

    finally:
        archiver.shutdown()
