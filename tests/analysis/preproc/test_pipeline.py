import dataclasses

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.preproc.flightfilter import DROP_TOO_SHORT
from soaring.analysis.preproc.pipeline import (
    FIX_TABLE_COLUMNS,
    PIPELINE_VERSION,
    run_flight,
)
from soaring.analysis.preproc.trimming import DROP_NO_FLIGHT
from soaring.analysis.preprocessing import load_preproc_config

CFG = load_preproc_config()
LAT0, LON0 = 45.0, 7.0
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = _M_PER_DEG_LAT * np.cos(np.radians(LAT0))


def _xc_track(duration_s=3000.0, ground_s=120.0, baro=True):
    """A plausible cross-country flight: ground, a climbing/gliding cruise, ground.

    Long enough and far enough to clear every flight-level cut, so that what the test
    exercises is the chain itself and not one of its gates.
    """
    n_air = int(duration_s)
    t_air = np.arange(n_air, dtype=float)
    east = 12.0 * t_air
    north = 200.0 * np.sin(2.0 * np.pi * t_air / 600.0)
    alt = 1200.0 + 400.0 * (1.0 - np.cos(2.0 * np.pi * t_air / 900.0))

    ground = int(ground_s)
    t = np.arange(n_air + 2 * ground, dtype=float)
    east = np.concatenate([np.zeros(ground), east, np.full(ground, east[-1])])
    north = np.concatenate([np.zeros(ground), north, np.full(ground, north[-1])])
    alt = np.concatenate([np.full(ground, alt[0]), alt, np.full(ground, alt[-1])])
    return pd.DataFrame(
        {
            "t": t,
            "lat": LAT0 + north / _M_PER_DEG_LAT,
            "lon": LON0 + east / _M_PER_DEG_LON,
            "valid": np.full(t.size, True),
            "baro_alt": alt if baro else np.zeros(t.size),
            "gnss_alt": alt + 50.0,
        }
    )


def _run(track):
    return run_flight(
        track, CFG, source="paraglider", flight_id="42", discipline="paragliders"
    )


def test_a_plausible_flight_comes_out_the_far_end():
    out = _run(_xc_track())

    assert out.kept
    assert out.meta.drop_reason is None
    assert out.meta.pipeline_version == PIPELINE_VERSION
    assert list(out.fixes.columns) == FIX_TABLE_COLUMNS
    assert (out.fixes["source"] == "paraglider").all()
    assert (out.fixes["flight_id"] == "42").all()
    # Every stage left its mark on the flights_meta row.
    assert out.meta.alt_source == "baro"
    assert out.meta.n_fix_raw == 3240
    assert out.meta.dt_native_s == pytest.approx(1.0)
    assert out.meta.savgol_window_horiz == 5
    assert out.meta.n_segments_kept == 1
    assert out.meta.lat0 == pytest.approx(LAT0, abs=1e-3)


def test_the_clock_starts_at_free_flight_and_the_frame_at_its_first_fix():
    out = _run(_xc_track())

    # sec:notation: r(0) = 0 with the clock reset at the first fix of the trimmed track.
    assert out.fixes["t"].iloc[0] == pytest.approx(0.0)
    assert out.fixes["E"].iloc[0] == pytest.approx(0.0, abs=1e-6)
    assert out.fixes["N"].iloc[0] == pytest.approx(0.0, abs=1e-6)
    # The ground phase is gone, and where it was is on the record. A pilot standing
    # still writes byte-identical positions, so the ground phase is *also* a frozen-lock
    # run: cleaning deletes it before trimming ever sees it, and the greedy run reaches
    # the first fix or two of the launch, which have not yet moved delta_xy away.
    assert 120.0 <= out.meta.ground_phase_start_s <= 124.0
    # So `trimmed_fraction` is trimming's own marginal share, and it is legitimately
    # zero here: by the time trimming looked, there was no ground phase left to cut.
    assert out.meta.trimmed_fraction == 0.0
    assert out.fixes["t"].iloc[-1] == pytest.approx(2999.0, abs=15.0)
    # z is the altitude, never re-zeroed.
    assert out.fixes["z"].iloc[0] == pytest.approx(1200.0, abs=5.0)


def test_the_kinematics_are_physical():
    out = _run(_xc_track())
    speed = np.hypot(out.fixes["v_E"], out.fixes["v_N"])
    interior = ~out.fixes["edge"]

    assert speed[interior].median() == pytest.approx(12.0, rel=0.05)
    assert float(speed.max()) < CFG.fix.max_horizontal_speed_mps["paragliders"]
    assert float(np.abs(out.fixes["v_z"]).max()) < CFG.fix.max_vertical_speed_mps
    assert np.isfinite(out.fixes[["E", "N", "z", "v_E", "a_E"]].to_numpy()).all()


def test_a_gnss_fallback_flight_runs_the_same_chain():
    out = _run(_xc_track(baro=False))
    assert out.kept
    assert out.meta.alt_source == "gnss"
    assert out.meta.baro_present_frac == 0.0
    assert out.meta.savgol_window_vert == 5


def test_a_flight_that_never_took_off_stops_at_trimming():
    track = _xc_track()
    track["lon"] = LON0  # never moves
    out = _run(track)

    assert not out.kept
    assert out.meta.drop_stage == "trimming"
    assert out.meta.drop_reason == DROP_NO_FLIGHT
    assert out.fixes.empty
    # The row still exists: the census of removals is a result too.
    assert out.meta.n_fix_raw == 3240
    assert out.meta.alt_source == "baro"


def test_a_sled_run_stops_at_the_flight_filter():
    out = _run(_xc_track(duration_s=900.0))

    assert not out.kept
    assert out.meta.drop_stage == "flight_filter"
    assert out.meta.drop_reason == DROP_TOO_SHORT
    # Just under the 900 s of recorded free flight: the fixes the frozen ground phase
    # took with it, and the one step across the split it left behind.
    assert 890.0 <= out.meta.duration_flight_s <= 899.0
    assert out.meta.path_km > 0.0  # measured, then judged


def test_a_frozen_lock_run_splits_the_flight_end_to_end():
    # The one defect that travels the whole length of the pipeline: cleaning marks the
    # run as a gap, resampling realises the split, and the smoothing never runs a window
    # across it.
    track = _xc_track()
    frozen = slice(1000, 1120)
    track.loc[frozen, "lat"] = track.loc[1000, "lat"]
    track.loc[frozen, "lon"] = track.loc[1000, "lon"]
    out = _run(track)

    assert out.kept
    assert out.meta.n_removed_frozen >= 120
    assert out.meta.n_segments == 2
    assert out.fixes["segment_id"].nunique() == 2
    # A segment keeps the parent clock: the second one does not restart at zero.
    second = out.fixes[out.fixes["segment_id"] == 1]
    assert second["t"].iloc[0] > 800.0


def test_every_table_carries_the_primary_key():
    """All *four* tables, and the fixture has to produce all four.

    The test was named for every table and checked two of them, and its "suspect stint"
    fixture produced none -- so `suspect_intervals`, the table stage (iii) exists to
    produce and which the psi(tau) sensitivity check consumes, was never looked at. A
    stint is reported only when it is slow, flat and lasts at least `frozen_tau_s`, so
    the fixture has to hold the position *and* the altitude still for long enough.
    """
    # Slow and flat, but *not* frozen: a pilot standing on a hillside wanders further
    # than the frozen-lock diameter, so stage (ii) leaves the run alone and stage (iii)
    # is the one that sees it. Shorter than `interior_ground_s`, so it is flagged rather
    # than excised, which is the case the table exists for.
    rng = np.random.default_rng(2)
    span = int(1.5 * CFG.fix.frozen_tau_s)
    stop = 1500 + span
    wander = 40.0 * np.sin(np.linspace(0.0, 2.0 * np.pi, span + 1))
    track = _xc_track()
    track.loc[1500:stop, "lat"] = track.loc[1500, "lat"] + wander / 111_320.0
    track.loc[1500:stop, "lon"] = track.loc[1500, "lon"]
    flat = track.loc[1500, "baro_alt"] + rng.normal(0.0, 0.5, span + 1)
    track.loc[1500:stop, "baro_alt"] = flat
    track.loc[1500:stop, "gnss_alt"] = flat + 47.0
    out = _run(track)

    for table in (out.fixes, out.segments, out.suspect_intervals):
        assert list(table.columns)[:2] == ["source", "flight_id"], table.columns
    assert list(out.segments.columns)[:3] == ["source", "flight_id", "segment_id"]
    assert len(out.suspect_intervals) or out.meta.n_interior_excised, (
        "the fixture produced neither a suspect stint nor an excision, so the fourth "
        "table was not exercised"
    )


def test_the_documented_fix_schema_matches_the_code():
    """The developer guide's column table is a contract, so it is checked, not trusted.

    Both guides were stale within hours of a column being added: `docs/` listed fifteen
    of the eighteen columns, typed `flight_id` as `int32` where it is written as a
    string, and named five `flights_meta` fields that do not exist. Prose drifts; a test
    does not.
    """
    import re
    from pathlib import Path

    from soaring.analysis.preproc.pipeline import FIX_TABLE_COLUMNS, FlightRecord

    root = Path(__file__).resolve().parents[3]
    guide = (root / "docs" / "guide" / "preprocessing-pipeline.md").read_text()
    documented = set()
    for row in re.findall(r"^\| `([^|]+?)` \|", guide, re.M):
        documented |= {name.strip(" `") for name in row.split("`, `")}
    missing = [c for c in FIX_TABLE_COLUMNS if c not in documented]
    assert not missing, f"columns written but not documented: {missing}"

    on_disk = (root / "docs" / "guide" / "data-on-disk.md").read_text()
    fields = [f.name for f in dataclasses.fields(FlightRecord)]
    absent = [f for f in fields if f"`{f}`" not in on_disk]
    assert not absent, f"flights_meta fields absent from data-on-disk.md: {absent}"
