import logging
import string
from random import randint, random, choice

from isac import IsacValue
from isac.tools import green

import alidron_archiver as arch

from test_tools import *

# logging.basicConfig(level=logging.WARNING)

def test_types_all(config, clean_db, one_node):
    t_start = datetime.now()
    iv = IsacValue(one_node, 'test://test_types/test_types_all/test', survey_last_value=False, survey_static_tags=False)

    try:
        archiver = arch.InfluxDBArchiver(config)

        expected_history = []
        def _save_point():
            value, ts, tags = iv.value_ts_tags
            ts = degrade_time(ts)
            expected_history.append((value, ts, tags))

        iv.value = randint(0, 100)
        _save_point()
        iv.value = random()*100
        _save_point()
        iv.value = False
        _save_point()
        iv.value = True
        _save_point()
        iv.value = ''.join(choice(string.ascii_uppercase + string.digits) for _ in range(16))
        _save_point()
        iv.value = {'a': 1, 'b': 2, 'c': 3}
        _save_point()

        t_end = datetime.now()

        data = iv.get_history((t_start, t_end))

        assert len(data) == len(expected_history)
        for got, expected in zip(data, expected_history):
            if isinstance(expected[0], float):
                assert abs(got[0] - expected[0]) < 1e-10
                assert got[1:] == expected[1:]
            else:
                assert got == expected

    finally:
        archiver.shutdown()
