import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.census import (
    _fix_level_arrays,
    fix_level_distributions,
    fraction_retained,
    great_circle_m,
    load_or_scan_fixlevel,
    load_or_scan_tracks,
    retention_curve,
    track_stats,
)
from soaring.analysis.config import load_preproc_config

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_flight.igc"


def test_load_preproc_config_from_yaml():
    # The authoritative values live in configs/preprocessing.yaml, not in code defaults.
    cfg = load_preproc_config()
    assert cfg.fix.max_horizontal_speed_mps == {
        "paragliders": 45.0,
        "hang gliders": 55.0,
    }
    assert cfg.fix.max_vertical_speed_mps == 30.0
    assert cfg.fix.vz_window_s == 5.0
    assert cfg.fix.vz_min_window_fixes == 5
    assert cfg.fix.hampel_window_s == 20.0
    assert cfg.fix.hampel_k == 5.0
    assert cfg.fix.hampel_eps_min_m == 15.0
    assert cfg.fix.frozen_tau_s == 60.0
    assert cfg.fix.integrity_max_fraction == pytest.approx(0.10)
    assert cfg.alt_channel.gnss_present_min == 0.95
    assert cfg.alt_channel.gnss_min_range_m == 30.0
    assert cfg.alt_channel.baro_witness_present_min == 0.95
    assert cfg.alt_channel.baro_witness_min_range_m == 30.0
    assert cfg.trimming.takeoff_speed_mps == 5.0
    assert cfg.trimming.sustained_s == 30.0
    assert cfg.trimming.interior_ground_s == 600.0
    assert cfg.flight.min_duration_s == 2400.0  # 40 min
    assert cfg.flight.min_path_km == 20.0
    assert cfg.flight.max_duration_s == 57600.0  # 16 h
    assert cfg.flight.min_alt_range_m == 600.0
    assert cfg.sampling.max_gap_factor == 10.0
    assert cfg.sampling.max_gap_seconds == 20.0
    assert cfg.sampling.max_missing_fraction == pytest.approx(0.10)
    assert cfg.sampling.min_segment_duration_s == 90.0
    assert cfg.savgol.polyorder == 3
    assert cfg.savgol.tau_c_horizontal_s == 5.0  # measured, estimate_savgol_timescales


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


def test_fix_level_arrays_gnss_present():
    # Per-FIX quantities (not per-flight): n-1 speeds, n altitudes, on a GNSS flight.
    # The vertical ones read the adopted (GNSS) channel, not the barometric witness
    # beside it -- the two are given different values here precisely to catch a
    # regression that reads the wrong one.
    fixes = pd.DataFrame(
        {
            "t": [0.0, 10.0, 20.0, 30.0],
            "lat": [0.0, 0.0, 0.0, 0.0],
            "lon": [0.0, 0.003, 0.006, 0.010],
            "valid": [True, True, True, True],
            "baro_alt": [999.0, 999.0, 999.0, 999.0],  # deliberately flat and distinct
            "gnss_alt": [100.0, 120.0, 110.0, 130.0],
        }
    )
    a = _fix_level_arrays(fixes)
    assert a["v_xy"].shape == (3,)
    assert a["altitude"].tolist() == [100.0, 120.0, 110.0, 130.0]
    # |delta gnss| / dt: |120-100|/10, |110-120|/10, |130-110|/10.
    assert a["v_z"] == pytest.approx([2.0, 1.0, 2.0])
    assert a["v_z_local"].shape == (3,)


def test_fix_level_arrays_repairs_a_backward_timestamp_before_windowing():
    # This reads a RAW parsed track, unlike clean_flight's own call site, where stage
    # (ii) has already repaired the time base by the time local_vz runs. A backward
    # step or a duplicate second here used to reach pandas' rolling() directly and
    # raise "index values must be monotonic" -- found running this diagnostic against
    # the real archive, where such defects are exactly what stage (ii) exists for.
    fixes = pd.DataFrame(
        {
            "t": [0.0, 10.0, 3.0, 20.0, 20.0, 30.0],  # backward step, then a duplicate
            "lat": [0.0] * 6,
            "lon": [0.0, 0.003, 0.0009, 0.006, 0.006, 0.009],
            "valid": [True] * 6,
            "baro_alt": [950.0, 970.0, 953.0, 990.0, 990.0, 1010.0],
            "gnss_alt": [1000.0, 1020.0, 1003.0, 1040.0, 1040.0, 1060.0],
        }
    )
    a = _fix_level_arrays(fixes)  # must not raise
    assert a["v_z_local"].size > 0
    assert np.all(np.isfinite(a["v_z_local"]))


def test_fix_level_arrays_no_usable_gnss_excludes_vertical():
    # A flight whose adopted channel is absent (sec:altchannel): vertical speed and
    # altitude are not measurements there, so they must be excluded; horizontal speed,
    # which needs neither channel, is kept regardless.
    fixes = pd.DataFrame(
        {
            "t": [0.0, 10.0, 20.0],
            "lat": [0.0, 0.0, 0.0],
            "lon": [0.0, 0.003, 0.006],
            "valid": [True, True, True],
            "baro_alt": [105.0, 115.0, 125.0],
            "gnss_alt": [0.0, 0.0, 0.0],
        }
    )
    a = _fix_level_arrays(fixes)
    assert a["v_xy"].shape == (2,)
    assert a["v_z"].size == 0
    assert a["v_z_local"].size == 0
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
    # The fixture has four fixes, but its GNSS channel drops to zero at one of them
    # (75 % present) -- below the channel gate, so the vertical quantities are excluded
    # exactly as a flight with no usable GNSS altitude would be at the real gate
    # (sec:altchannel). Horizontal speed needs neither channel and is unaffected.
    assert d["v_xy"].shape == (3,)
    assert d["v_z"].size == 0
    assert d["v_z_local"].size == 0
    assert d["altitude"].size == 0


def test_load_or_scan_fixlevel_caches(tmp_path):
    igc_dir = tmp_path / "igc"
    igc_dir.mkdir()
    shutil.copy(FIXTURE, igc_dir / "sample_flight.igc")
    cache_path = tmp_path / "fixlevel_scan.parquet"

    assert not cache_path.exists()
    first = load_or_scan_fixlevel(igc_dir, cache_path, n=1)
    assert cache_path.is_file()
    # Matches fix_level_distributions([FIXTURE]) directly (same fixture, same sample):
    # the horizontal speed is populated, the GNSS-gated quantities are empty (see
    # test_fix_level_distributions_pools_fixture) -- the cache must round-trip the
    # empty arrays too, not just the populated one.
    assert first["v_xy"].shape == (3,)
    assert first["v_z"].size == 0
    assert first["v_z_local"].size == 0
    assert first["altitude"].size == 0

    # Second call must read the cache, not resample: delete the source and confirm it
    # still returns the cached values instead of silently finding zero flights.
    (igc_dir / "sample_flight.igc").unlink()
    second = load_or_scan_fixlevel(igc_dir, cache_path, n=1)
    for key in first:
        np.testing.assert_allclose(second[key], first[key], rtol=1e-5)

    # force=True must resample even though the cache exists -- with the source gone,
    # that means an empty sample (sample_igc_paths finds nothing under an empty dir).
    third = load_or_scan_fixlevel(igc_dir, cache_path, n=1, force=True)
    assert all(v.size == 0 for v in third.values())
