import numpy as np
import pandas as pd
import pytest

from soaring.analysis.preprocessing import (
    FixLevelThresholds,
    FlightLevelThresholds,
    approx_num_fixes,
    fraction_retained,
    retention_curve,
)


def test_threshold_defaults():
    fx = FixLevelThresholds()
    assert fx.max_horizontal_speed_mps == 40.0
    assert fx.max_vertical_speed_mps == 10.0
    assert fx.min_altitude_m == -100.0
    assert fx.max_altitude_m == 6000.0
    ft = FlightLevelThresholds()
    assert ft.min_duration_s == 1800.0
    assert ft.min_valid_fixes == 200
    assert ft.min_extent_km == 2.0


def test_fraction_retained_basic():
    v = [0, 1, 2, 3, 4]
    assert fraction_retained(v, 2) == pytest.approx(0.6)
    assert fraction_retained(v, 0) == pytest.approx(1.0)
    assert fraction_retained(v, 10) == pytest.approx(0.0)


def test_fraction_retained_ignores_nan():
    assert fraction_retained([np.nan, 1.0, 3.0], 2.0) == pytest.approx(0.5)


def test_fraction_retained_empty():
    assert fraction_retained([np.nan, np.nan], 1.0) == 0.0


def test_retention_curve_is_non_increasing():
    thr, frac = retention_curve(np.arange(100), [0, 25, 50, 75, 100])
    assert list(thr) == [0, 25, 50, 75, 100]
    assert frac[0] == pytest.approx(1.0)
    assert np.all(np.diff(frac) <= 0)


def test_approx_num_fixes():
    got = approx_num_fixes(pd.Series([40, 400, 4000]))
    assert list(got) == [1.0, 10.0, 100.0]
