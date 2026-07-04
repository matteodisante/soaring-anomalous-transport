import numpy as np
import pandas as pd
import pytest

from soaring.analysis.preprocessing import (
    fraction_retained,
    great_circle_m,
    load_preproc_config,
    retention_curve,
    track_stats,
)


def test_load_preproc_config_from_yaml():
    # The authoritative values live in configs/preprocessing.yaml, not in code defaults.
    cfg = load_preproc_config()
    assert cfg.fix.max_horizontal_speed_mps == 40.0
    assert cfg.fix.max_vertical_speed_mps == 10.0
    assert cfg.trimming.takeoff_speed_mps == 5.0
    assert cfg.trimming.sustained_s == 30.0
    assert cfg.flight.min_duration_s == 2400.0  # 40 min
    assert cfg.flight.min_path_km == 30.0
    assert cfg.sampling.max_missing_fraction == pytest.approx(0.10)
    assert cfg.savgol.polyorder == 3


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


def test_great_circle_m_known_distance():
    # One degree of latitude is ~111 km along a meridian.
    d = great_circle_m(0.0, 0.0, np.array([1.0]), np.array([0.0]))
    assert d[0] == pytest.approx(111195.0, rel=1e-3)
    # Zero distance to itself.
    assert great_circle_m(45.0, 7.0, np.array([45.0]), np.array([7.0]))[0] == 0.0


def test_great_circle_m_consecutive_steps():
    # Aligned arrays: distance between successive points, element-wise.
    lat = np.array([0.0, 0.0, 0.0])
    lon = np.array([0.0, 0.001, 0.003])
    steps = great_circle_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    assert steps.shape == (2,)
    assert steps[1] == pytest.approx(2.0 * steps[0], rel=1e-6)  # 0.002 vs 0.001 deg


def test_track_stats_from_fixes():
    # Straight eastward motion: path length equals extent; dt = 10 s.
    fixes = pd.DataFrame(
        {
            "t": [0.0, 10.0, 20.0, 30.0],
            "lat": [0.0, 0.0, 0.0, 0.0],
            "lon": [0.0, 0.003, 0.006, 0.010],
            "valid": [True, True, True, True],
            "baro_alt": [100.0, 110.0, 120.0, 130.0],
            "gnss_alt": [105.0, 115.0, 125.0, 135.0],
        }
    )
    stats = track_stats(fixes)
    assert stats["duration_s"] == pytest.approx(30.0)
    assert stats["n_fix"] == 4
    assert stats["dt_s"] == pytest.approx(10.0)
    assert stats["extent_km"] == pytest.approx(1.113, rel=1e-2)
    # Monotonic straight track: total path length equals the extent.
    assert stats["path_km"] == pytest.approx(stats["extent_km"], rel=1e-6)


def test_track_stats_too_short_is_none():
    fixes = pd.DataFrame(
        {c: [0.0] for c in ["t", "lat", "lon", "valid", "baro_alt", "gnss_alt"]}
    )
    assert track_stats(fixes) is None
