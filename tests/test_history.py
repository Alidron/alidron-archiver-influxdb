# Copyright (c) 2015-2016 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

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

def test_get_history(config, clean_db, two_nodes):
    nA, nB = two_nodes
    t_start = datetime.now()

    uri = 'test://test_history/test_get_history/test'
    ivA = IsacValue(nA, uri, survey_last_value=False, survey_static_tags=False)

    try:
        archiver = arch.InfluxDBArchiver(config)

        our_history = []
        for i in range(10):
            ivA.value = randint(0, 100)
            value, ts, tags = ivA.value_ts_tags
            ts = degrade_time(ts)
            our_history.append((value, ts, tags))
        green.sleep(0.5)
        t_end = datetime.now()

        ivB = IsacValue(nB, uri, survey_last_value=False, survey_static_tags=False)
        data = ivB.get_history((t_start, t_end))
        assert data == our_history
    finally:
        archiver.shutdown()

# TODO: test various time periods
