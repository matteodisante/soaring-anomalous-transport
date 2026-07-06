import pandas as pd

from soaring.analysis.altitude_noise import baro_presence_from_scan


def test_baro_presence_from_scan_counts_absent():
    # BARO_PRESENT_MIN = 0.5: the two flights at 0.0 and 0.1 count as absent.
    scan = pd.DataFrame({"baro_present_frac": [1.0, 0.0, 0.9, 0.1, 0.6]})
    absent, n = baro_presence_from_scan(scan)
    assert n == 5
    assert absent == 2


def test_baro_presence_from_scan_all_present():
    scan = pd.DataFrame({"baro_present_frac": [1.0, 0.95, 0.8]})
    absent, n = baro_presence_from_scan(scan)
    assert absent == 0
    assert n == 3
