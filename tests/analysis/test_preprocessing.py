import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.preprocessing import (
    _fix_level_arrays,
    fix_level_distributions,
    fraction_retained,
    great_circle_m,
    load_or_scan_tracks,
    load_preproc_config,
    retention_curve,
    track_stats,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_flight.igc"


def test_load_preproc_config_from_yaml():
    # The authoritative values live in configs/preprocessing.yaml, not in code defaults.
    cfg = load_preproc_config()
    assert cfg.fix.max_horizontal_speed_mps == {
        "paragliders": 45.0,
        "hang gliders": 55.0,
    }
    assert cfg.fix.max_vertical_speed_mps == {
        "paragliders": 12.0,
        "hang gliders": 14.0,
    }
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
    # Perfectly uniform 10 s cadence: no gap beyond native dt, nothing missing.
    assert stats["max_gap_ratio"] == pytest.approx(1.0)
    assert stats["missing_fraction"] == pytest.approx(0.0)


def test_track_stats_too_short_is_none():
    fixes = pd.DataFrame(
        {c: [0.0] for c in ["t", "lat", "lon", "valid", "baro_alt", "gnss_alt"]}
    )
    assert track_stats(fixes) is None


def test_track_stats_detects_a_gap():
    # Uniform at 10 s, except one gap of 50 s (5x native) -> missing several samples.
    fixes = pd.DataFrame(
        {
            "t": [0.0, 10.0, 20.0, 70.0, 80.0],
            "lat": [0.0, 0.0, 0.0, 0.0, 0.0],
            "lon": [0.0, 0.003, 0.006, 0.021, 0.024],
            "valid": [True] * 5,
            "baro_alt": [100.0] * 5,
            "gnss_alt": [105.0] * 5,
        }
    )
    stats = track_stats(fixes)
    assert stats["dt_s"] == pytest.approx(10.0)
    assert stats["max_gap_ratio"] == pytest.approx(5.0)
    # duration=80s, dt=10s -> 9 expected samples on a uniform grid, only 5 present.
    assert stats["missing_fraction"] == pytest.approx(1.0 - 5.0 / 9.0, rel=1e-6)


def test_fraction_retained_at_most_mode():
    v = [0, 1, 2, 3, 4]
    assert fraction_retained(v, 2, mode="at_most") == pytest.approx(0.6)
    assert fraction_retained(v, -1, mode="at_most") == pytest.approx(0.0)
    assert fraction_retained(v, 10, mode="at_most") == pytest.approx(1.0)


def test_track_stats_extra_fields():
    # Nearly-free byproducts of the same scan: baro presence, speed/altitude extremes.
    fixes = pd.DataFrame(
        {
            "t": [0.0, 10.0, 20.0, 30.0],
            "lat": [0.0, 0.0, 0.0, 0.0],
            "lon": [0.0, 0.003, 0.006, 0.010],
            "valid": [True, True, True, True],
            "baro_alt": [100.0, 110.0, 90.0, 100.0],
            "gnss_alt": [105.0, 115.0, 125.0, 135.0],
        }
    )
    stats = track_stats(fixes)
    assert stats["baro_present_frac"] == pytest.approx(1.0)
    assert stats["baro_alt_min_m"] == pytest.approx(90.0)
    assert stats["baro_alt_max_m"] == pytest.approx(110.0)
    # max |delta baro_alt| is 20 m (110 -> 90), over 10 s -> 2 m/s.
    assert stats["max_vz_mps"] == pytest.approx(2.0, rel=1e-6)
    # max horizontal step is the last one (0.004 deg vs 0.003 deg), over the same 10 s.
    last_step_m = great_circle_m(0.0, 0.006, 0.0, 0.010)
    assert stats["max_vxy_mps"] == pytest.approx(float(last_step_m) / 10.0, rel=1e-6)


def test_load_or_scan_tracks_caches(tmp_path):
    igc_dir = tmp_path / "igc"
    igc_dir.mkdir()
    shutil.copy(FIXTURE, igc_dir / "sample_flight.igc")
    cache_path = tmp_path / "track_scan.parquet"

    assert not cache_path.exists()
    first = load_or_scan_tracks(igc_dir, cache_path)
    assert cache_path.is_file()
    assert len(first) == 1

    # Second call must read the cache, not rescan: delete the source and confirm it
    # still returns the cached row instead of silently finding zero flights.
    (igc_dir / "sample_flight.igc").unlink()
    second = load_or_scan_tracks(igc_dir, cache_path)
    pd.testing.assert_frame_equal(first, second)


def test_fix_level_arrays_baro_present():
    # Per-FIX quantities (not per-flight): n-1 speeds, n altitudes, on a baro flight.
    fixes = pd.DataFrame(
        {
            "t": [0.0, 10.0, 20.0, 30.0],
            "lat": [0.0, 0.0, 0.0, 0.0],
            "lon": [0.0, 0.003, 0.006, 0.010],
            "valid": [True, True, True, True],
            "baro_alt": [100.0, 120.0, 110.0, 130.0],
            "gnss_alt": [105.0, 115.0, 125.0, 135.0],
        }
    )
    a = _fix_level_arrays(fixes)
    assert a["v_xy"].shape == (3,)
    assert a["altitude"].tolist() == [100.0, 120.0, 110.0, 130.0]
    # |delta baro| / dt: |120-100|/10, |110-120|/10, |130-110|/10.
    assert a["v_z"] == pytest.approx([2.0, 1.0, 2.0])


def test_fix_level_arrays_gnss_only_excludes_vertical():
    # A logger with no pressure sensor writes baro as zero: vertical speed and altitude
    # are not measurements there, so they must be excluded; horizontal speed is kept.
    fixes = pd.DataFrame(
        {
            "t": [0.0, 10.0, 20.0],
            "lat": [0.0, 0.0, 0.0],
            "lon": [0.0, 0.003, 0.006],
            "valid": [True, True, True],
            "baro_alt": [0.0, 0.0, 0.0],
            "gnss_alt": [105.0, 115.0, 125.0],
        }
    )
    a = _fix_level_arrays(fixes)
    assert a["v_xy"].shape == (2,)
    assert a["v_z"].size == 0
    assert a["altitude"].size == 0


def test_fix_level_arrays_drops_nonpositive_dt():
    # Duplicate timestamps (dt <= 0) must not produce an inf/undefined speed.
    fixes = pd.DataFrame(
        {
            "t": [0.0, 0.0, 10.0],
            "lat": [0.0, 0.0, 0.0],
            "lon": [0.0, 0.003, 0.006],
            "valid": [True, True, True],
            "baro_alt": [100.0, 110.0, 120.0],
            "gnss_alt": [105.0, 115.0, 125.0],
        }
    )
    a = _fix_level_arrays(fixes)
    assert a["v_xy"].shape == (1,)  # only the one pair with dt > 0
    assert np.all(np.isfinite(a["v_xy"]))


def test_fix_level_distributions_pools_fixture():
    d = fix_level_distributions([FIXTURE])
    # the fixture has four fixes and a present barometric channel.
    assert d["v_xy"].shape == (3,)
    assert d["v_z"].shape == (3,)
    assert d["altitude"].shape == (4,)
