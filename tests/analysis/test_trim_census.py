"""``trim_split_one``/``scan_trim_split``/``load_or_scan_trim_split`` (sec:trimming).

``flights_meta.parquet`` keeps only the *combined* trimmed fraction; these functions
rerun stages (i)-(iii) to recover the takeoff/landing split that table does not carry
(module docstring, ``soaring.analysis.trim_census``).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.trim_census import (
    load_or_scan_trim_split,
    scan_trim_split,
    trim_split_one,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_flight.igc"
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = _M_PER_DEG_LAT * np.cos(np.radians(45.0))


def _write_igc(path: Path, t, lat, lon, alt) -> None:
    """A minimal IGC file: header plus one B record per sample, 1 Hz from midnight."""
    lines = ["AXXXsoaring test fixture"]
    for tt, la, lo, al in zip(t, lat, lon, alt, strict=True):
        hh, rem = divmod(int(tt), 3600)
        mm, ss = divmod(rem, 60)
        lat_deg, lat_min = int(abs(la)), (abs(la) - int(abs(la))) * 60
        lon_deg, lon_min = int(abs(lo)), (abs(lo) - int(abs(lo))) * 60
        ns = "N" if la >= 0 else "S"
        ew = "E" if lo >= 0 else "W"
        lat_s = f"{lat_deg:02d}{lat_min * 1000:05.0f}{ns}"
        lon_s = f"{lon_deg:03d}{lon_min * 1000:05.0f}{ew}"
        alt_s = f"{int(al):05d}"
        lines.append(f"B{hh:02d}{mm:02d}{ss:02d}{lat_s}{lon_s}A{alt_s}{alt_s}")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _synthetic_flight() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Ground, 300 s cruise at 12 m/s, ground: a genuine takeoff- and landing-trim.

    Both ground stretches stay just *under* ``frozen_tau_s`` (60 s): byte-identical
    coordinates held for 60 s or longer are the frozen-lock rule's own witness
    (sec:fixlevel) and get deleted in stage (ii), before trim_flight ever sees them as
    a ground phase to trim in stage (iii) -- a real interaction between the two rules,
    caught by an earlier version of this fixture spanning exactly 60 s.
    """
    ground_before = np.arange(0, 45, 1.0)  # 44 s span
    cruise = 45 + np.arange(0, 300, 1.0)
    ground_after = 345 + np.arange(0, 40, 1.0)  # 39 s span
    t = np.concatenate([ground_before, cruise, ground_after])
    east = np.zeros_like(t)
    east[t >= 45] = 12.0 * (t[t >= 45] - 45.0)
    east[t >= 345] = east[np.searchsorted(t, 345.0) - 1]
    lat = np.full_like(t, 45.0)
    lon = 7.0 + east / _M_PER_DEG_LON
    alt = 1500.0 + 2.0 * t
    return t, lat, lon, alt


def test_trim_split_one_is_none_for_a_gnss_gated_fixture():
    # sample_flight.igc is a 4-fix parser fixture below the GNSS presence/range floor
    # (soaring.analysis.preproc.altchannel), so it never reaches trim_flight at all --
    # there is no [t_on, t_off] to split a duration around.
    assert trim_split_one(FIXTURE, "paragliders") is None


def test_trim_split_one_splits_the_combined_fraction_by_end(tmp_path):
    t, lat, lon, alt = _synthetic_flight()
    path = tmp_path / "flight.igc"
    _write_igc(path, t, lat, lon, alt)

    result = trim_split_one(path, "paragliders")
    assert result is not None
    takeoff_trimmed_s, landing_trimmed_s, n_interior_excised = result

    # The ground stretch before/after the cruise is what gets trimmed at each end.
    assert takeoff_trimmed_s == pytest.approx(45.0, abs=2.0)
    assert landing_trimmed_s == pytest.approx(40.0, abs=2.0)
    assert n_interior_excised == 0


def test_scan_trim_split_drops_flights_with_no_window(tmp_path):
    igc_dir = tmp_path / "igc"
    igc_dir.mkdir()
    shutil.copy(FIXTURE, igc_dir / "sample_flight.igc")
    t, lat, lon, alt = _synthetic_flight()
    _write_igc(igc_dir / "real_flight.igc", t, lat, lon, alt)

    scan = scan_trim_split(sorted(igc_dir.glob("*.igc")), "paragliders", n_jobs=1)
    assert len(scan) == 1  # the GNSS-gated fixture contributes no row
    assert list(scan.columns) == [
        "takeoff_trimmed_s",
        "landing_trimmed_s",
        "n_interior_excised",
    ]


def test_load_or_scan_trim_split_caches(tmp_path):
    igc_dir = tmp_path / "igc"
    igc_dir.mkdir()
    t, lat, lon, alt = _synthetic_flight()
    _write_igc(igc_dir / "real_flight.igc", t, lat, lon, alt)
    cache_path = tmp_path / "trim_scan.parquet"

    assert not cache_path.exists()
    first = load_or_scan_trim_split(igc_dir, "paragliders", cache_path)
    assert cache_path.is_file()
    assert len(first) == 1

    # Second call must read the cache, not rescan: delete the source and confirm it
    # still returns the cached row instead of silently finding zero flights.
    (igc_dir / "real_flight.igc").unlink()
    second = load_or_scan_trim_split(igc_dir, "paragliders", cache_path)
    pd.testing.assert_frame_equal(first, second)


def test_load_or_scan_trim_split_force_rescans(tmp_path):
    igc_dir = tmp_path / "igc"
    igc_dir.mkdir()
    t, lat, lon, alt = _synthetic_flight()
    _write_igc(igc_dir / "real_flight.igc", t, lat, lon, alt)
    cache_path = tmp_path / "trim_scan.parquet"

    load_or_scan_trim_split(igc_dir, "paragliders", cache_path)
    (igc_dir / "real_flight.igc").unlink()
    forced = load_or_scan_trim_split(igc_dir, "paragliders", cache_path, force=True)
    assert len(forced) == 0  # the source is gone and the stale cache was not trusted
