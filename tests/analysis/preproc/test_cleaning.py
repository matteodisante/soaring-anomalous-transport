import numpy as np
import pandas as pd
import pytest

from soaring.analysis.preproc.cleaning import (
    DROP_INTEGRITY,
    REMOVED_BACKWARD_TIME,
    REMOVED_FROZEN_RUN,
    REMOVED_POSITION_SPIKE,
    clean_flight,
    hampel_flags,
    integrity_gate,
    longest_non_decreasing,
)
from soaring.analysis.config import load_preproc_config
from soaring.analysis.census import great_circle_m

FIX = load_preproc_config().fix
LAT0, LON0 = 45.0, 7.0
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = _M_PER_DEG_LAT * np.cos(np.radians(LAT0))


def _flight(east_m, north_m, alt_m, dt=1.0, valid=None):
    """A synthetic flight from local metric offsets, back on geographic coordinates."""
    east_m = np.asarray(east_m, dtype=float)
    north_m = np.asarray(north_m, dtype=float)
    n = east_m.size
    return pd.DataFrame(
        {
            "t": np.arange(n) * dt,
            "lat": LAT0 + north_m / _M_PER_DEG_LAT,
            "lon": LON0 + east_m / _M_PER_DEG_LON,
            "alt": np.broadcast_to(np.asarray(alt_m, dtype=float), (n,)).copy(),
            "valid": np.full(n, True)
            if valid is None
            else np.asarray(valid, dtype=bool),
        }
    )


def _glide(n=300, speed=10.0, dt=1.0, climb=-1.0, alt0=2000.0):
    """A straight glide: nothing for any detector to find."""
    t = np.arange(n) * dt
    return _flight(speed * t, np.zeros(n), alt0 + climb * t, dt=dt)


def _clean(flight, alt_source="baro"):
    return clean_flight(flight, FIX, discipline="paragliders", alt_source=alt_source)


# --------------------------------------------------------------------------------
# (1) Time-base defects
# --------------------------------------------------------------------------------


def test_longest_non_decreasing_keeps_ties_and_the_longest_run():
    assert longest_non_decreasing(np.array([0.0, 1.0, 2.0, 3.0])).tolist() == [
        0,
        1,
        2,
        3,
    ]
    # Ties are kept: two fixes in one second are a duplicate, not a backward step.
    assert longest_non_decreasing(np.array([0.0, 1.0, 1.0, 2.0])).tolist() == [
        0,
        1,
        2,
        3,
    ]
    # One fix with a forward-jumped clock removes itself, not everything after it.
    assert longest_non_decreasing(np.array([0.0, 99.0, 1.0, 2.0, 3.0])).tolist() == [
        0,
        2,
        3,
        4,
    ]


def test_a_backward_timestamp_is_removed_by_minimal_deletion():
    flight = _glide(n=60)
    flight.loc[30, "t"] = 999.0  # a forward-jumped clock, one fix
    out = _clean(flight)

    assert out.report.n_removed_backward == 1
    assert out.removed["reason"].tolist() == [REMOVED_BACKWARD_TIME]
    assert out.removed["t"].tolist() == [999.0]
    assert len(out.fixes) == 59  # every other fix survives
    assert np.all(np.diff(out.fixes["t"].to_numpy()) > 0)


def test_duplicate_seconds_merge_to_their_centroid():
    flight = _glide(n=20)
    doubled = pd.concat([flight, flight.iloc[[5]]], ignore_index=True)
    doubled.loc[20, "lon"] = flight.loc[5, "lon"] + 10.0 / _M_PER_DEG_LON  # 10 m apart
    doubled.loc[20, "valid"] = False
    out = _clean(doubled.sort_values("t").reset_index(drop=True))

    assert out.report.n_merged_duplicates == 1
    assert len(out.fixes) == 20
    merged = out.fixes[out.fixes["t"] == 5.0]
    # The centroid, not an arbitrary member: 5 m past the first of the pair.
    assert (merged["lon"].item() - flight.loc[5, "lon"]) * _M_PER_DEG_LON == (
        pytest.approx(5.0, abs=0.01)
    )
    # The V flag of either member survives the merge: it is their logical or.
    assert merged["valid"].item() is np.False_ or merged["valid"].item() is False


# --------------------------------------------------------------------------------
# (2) Position outliers: flag, then corroborate
# --------------------------------------------------------------------------------


def test_a_clean_glide_is_left_completely_alone():
    out = _clean(_glide())
    assert len(out.fixes) == 300
    assert out.removed.empty
    assert not out.fixes["hampel_flagged"].any()
    assert not out.fixes["alt_invalidated"].any()
    assert not out.fixes["split_before"].any()


def test_an_impossible_spike_is_flagged_and_deleted():
    flight = _glide()
    flight.loc[150, "lat"] += 100.0 / _M_PER_DEG_LAT  # 100 m sideways in one second
    out = _clean(flight)

    assert out.report.n_removed_spike == 1
    assert out.removed["reason"].tolist() == [REMOVED_POSITION_SPIKE]
    assert 150.0 not in out.fixes["t"].tolist()
    assert len(out.fixes) == 299


def test_a_flagged_but_possible_fix_is_kept_and_counted():
    # The corroboration is the whole point: 30 m off the trend at a 10 s cadence is an
    # ordinary 3 m/s, so the fix is anomalous but not impossible -- it stays, and the
    # flag is recorded as the per-flight anomaly count.
    flight = _glide(n=40, dt=10.0)
    flight.loc[20, "lat"] += 30.0 / _M_PER_DEG_LAT
    out = _clean(flight)

    assert out.report.n_removed_spike == 0
    assert out.report.n_flagged_kept >= 1
    assert out.fixes.loc[out.fixes["t"] == 200.0, "hampel_flagged"].item() is True
    assert len(out.fixes) == 40


def test_a_tight_thermalling_circle_is_never_deleted():
    # The failure mode the corroboration exists to prevent: consecutive fixes of a tight
    # circle genuinely sit on opposite sides of their own window median, but a circling
    # wing flies at an ordinary speed.
    n, radius, speed = 300, 15.0, 10.0
    t = np.arange(n, dtype=float)
    omega = speed / radius
    flight = _flight(
        radius * np.cos(omega * t), radius * np.sin(omega * t), 2000.0 + 2.0 * t
    )
    out = _clean(flight)

    assert out.report.n_removed_spike == 0
    assert len(out.fixes) == n


def test_a_burst_of_spikes_is_removed_as_one_block():
    flight = _glide()
    for i in (150, 151, 152):
        flight.loc[i, "lat"] += 150.0 / _M_PER_DEG_LAT
    out = _clean(flight)

    assert out.report.n_removed_spike == 3
    assert len(out.fixes) == 297
    assert not out.fixes["split_before"].any()  # the trend rejoined: no discontinuity


def test_a_reacquisition_offset_splits_instead_of_deleting():
    # The track jumps and stays: no bounded removal restores continuity, so both sides
    # are kept and only the transition between them is declared unknown. 4 km is the
    # realistic scale of a re-acquisition offset, and it is out of reach at the speed
    # bound for far longer than a block may run.
    flight = _glide()
    flight.loc[150:, "lat"] += 4000.0 / _M_PER_DEG_LAT
    out = _clean(flight)

    assert out.report.n_removed_spike == 0
    assert len(out.fixes) == 300  # nothing deleted
    assert out.report.n_splits == 1
    assert out.fixes.loc[out.fixes["split_before"], "t"].item() == pytest.approx(150.0)


def test_the_hampel_window_is_a_time_window_not_a_sample_count():
    """The rule under test is `hampel_min_window_fixes`, and this is its only test.

    It has been written to pass for the wrong reason twice. The first version fed a
    *clean* sparse track and asserted that nothing was flagged -- true whatever the
    config says, because there was nothing to flag. The second put an outlier on a 60 s
    track, where the +/- 20 s window holds a single fix and there are no neighbours at
    all, so again nothing is flagged for any value of the key.

    A test of a threshold has to straddle it. At a +/- 20 s half-width the window holds
    about ``2 * 20 / dt + 1`` fixes, so a 10 s cadence gives five -- exactly the
    configured minimum, where the identifier still runs -- and a 15 s cadence gives
    three, where it must abstain. The same outlier on both, and the verdict differs.
    Sweeping the key itself is what proves the test is measuring it and not something
    else.
    """
    import dataclasses

    def flags_at(dt, min_fixes=None):
        n = max(20, int(1200 / dt))
        track = _glide(n=n, dt=dt)
        track.loc[n // 2, "lat"] += 400.0 / _M_PER_DEG_LAT  # unmistakable, 400 m
        fix = (
            FIX
            if min_fixes is None
            else dataclasses.replace(FIX, hampel_min_window_fixes=min_fixes)
        )
        return int(
            hampel_flags(
                track["t"].to_numpy(),
                track["lat"].to_numpy(),
                track["lon"].to_numpy(),
                fix,
            ).sum()
        )

    assert flags_at(10.0) == 1, "five fixes in the window: the identifier must run"
    assert flags_at(15.0) == 0, "three fixes in the window: it must abstain"

    # And the verdict moves with the key, which is what makes this a test of it: the
    # sparse track is flagged once the minimum is lowered below its population, and the
    # dense one abstains once the minimum is raised above its own.
    assert flags_at(15.0, min_fixes=3) == 1
    assert flags_at(10.0, min_fixes=7) == 0


# --------------------------------------------------------------------------------
# (3) Frozen-lock runs
# --------------------------------------------------------------------------------


def _with_frozen_run(n=300, start=100, length=90, alt_climb=0.0, jitter=0.0):
    """A glide with a stretch of repeated positions in the middle."""
    east = 10.0 * np.arange(n, dtype=float)
    north = np.zeros(n)
    alt = 2000.0 - 1.0 * np.arange(n, dtype=float)
    stop = start + length
    east[start:stop] = east[start]
    north[start:stop] = north[start]
    if jitter:
        rng = np.random.default_rng(7)
        east[start:stop] += rng.normal(0.0, jitter, length)
        north[start:stop] += rng.normal(0.0, jitter, length)
    east[stop:] = east[start] + 10.0 * np.arange(1, n - stop + 1, dtype=float)
    if alt_climb:
        alt[start:stop] = alt[start] + alt_climb * np.arange(length, dtype=float)
        alt[stop:] = alt[stop - 1] - 1.0 * np.arange(n - stop, dtype=float)
    return _flight(east, north, alt)


def test_a_byte_identical_run_is_cut_and_split():
    out = _clean(_with_frozen_run())

    assert out.report.n_removed_frozen == 90
    assert set(out.removed["reason"]) == {REMOVED_FROZEN_RUN}
    assert len(out.fixes) == 210
    # Marked as a gap: the trajectory is split there rather than interpolated across.
    assert out.report.n_splits == 1
    assert out.fixes.loc[out.fixes["split_before"], "t"].item() == pytest.approx(190.0)


def test_a_short_frozen_run_is_kept_on_purpose():
    # Below tau_freeze the rule abstains: a collapsed run and a genuine slow, localized
    # stretch are not distinguishable by these signatures at a few tens of seconds.
    out = _clean(_with_frozen_run(length=45))
    assert out.report.n_removed_frozen == 0
    assert len(out.fixes) == 300


def test_a_climbing_barometer_defends_a_collapsed_run():
    # The independent-witness argument: a lock loss freezes the GNSS position while the
    # pressure sensor, a separate instrument, keeps recording a real climb. The
    # positions here jitter rather than repeat, so nothing overrules the barometer.
    out = _clean(_with_frozen_run(alt_climb=1.0, jitter=1.5))
    assert out.report.n_removed_frozen == 0
    assert len(out.fixes) == 300


def test_byte_identical_coordinates_overrule_a_climbing_barometer():
    # The one conclusive signature: no moving receiver rewrites the very same bits, so
    # the positions are invented whatever the barometer says.
    out = _clean(_with_frozen_run(alt_climb=1.0))
    assert out.report.n_removed_frozen == 90


def test_on_a_gnss_flight_the_recorder_declarations_are_the_witness():
    flight = _with_frozen_run(alt_climb=1.0, jitter=1.5)
    flight.loc[100:189, "valid"] = False
    out = _clean(flight, alt_source="gnss")
    # 90 frozen fixes, plus at most the first fix after them: the wing has not yet moved
    # delta_xy away, so a greedy collapsed run reaches it. A bounded over-cut, and the
    # only place the byte-identical family of candidates is not the one that fires.
    assert out.report.n_removed_frozen in (90, 91)
    assert not set(np.arange(100.0, 190.0)) & set(out.fixes["t"].tolist())


def test_an_undeclared_jittering_freeze_on_a_gnss_flight_is_kept():
    # The residual "wrongly kept" case sec:fixlevel names: neither byte-identical nor
    # declared, so nothing witnesses it and the default to keep wins.
    out = _clean(_with_frozen_run(jitter=1.5), alt_source="gnss")
    assert out.report.n_removed_frozen == 0


# --------------------------------------------------------------------------------
# (4) Altitude: absolute bounds only
# --------------------------------------------------------------------------------


def test_an_out_of_band_altitude_is_invalidated_and_the_fix_stays():
    flight = _glide()
    flight.loc[100, "alt"] = 9000.0  # above the sensor-plausibility window
    out = _clean(flight)

    assert out.report.n_alt_out_of_band == 1
    assert len(out.fixes) == 300  # the invariant: the position was never in question
    row = out.fixes[out.fixes["t"] == 100.0]
    assert np.isnan(row["alt"].item())
    assert row["alt_invalidated"].item() is True


def test_an_isolated_vertical_spike_is_invalidated():
    flight = _glide()
    flight.loc[100, "alt"] += 40.0  # up 40 m and back down within a second each way
    out = _clean(flight)

    assert out.report.n_alt_vz_spike == 1
    assert np.isnan(out.fixes.loc[out.fixes["t"] == 100.0, "alt"].item())
    assert len(out.fixes) == 300


def test_a_sustained_dive_is_not_censored_but_counted():
    # impl:fixlevel check (5): a run-shaped excess is a genuine manoeuvre -- a spiral
    # dive holds 15-20 m/s of real sink -- and calls for a raised bound, not censoring.
    flight = _glide()
    alt = flight["alt"].to_numpy(copy=True)
    alt[120:150] = alt[119] - 18.0 * np.arange(1, 31)
    alt[150:] = alt[149] - 1.0 * np.arange(1, len(alt) - 149)
    flight["alt"] = alt
    out = _clean(flight)

    assert out.report.n_alt_vz_spike == 0
    assert out.report.n_vz_runs == 1
    assert np.isfinite(out.fixes["alt"].to_numpy()).all()


def test_the_v_flag_invalidates_only_on_a_gnss_flight():
    flight = _glide()
    flight.loc[100:104, "valid"] = False

    on_baro = _clean(flight, alt_source="baro")
    assert on_baro.report.n_alt_out_of_band == 0
    assert not on_baro.fixes["alt_invalidated"].any()  # a V certifies the GNSS altitude

    on_gnss = _clean(flight, alt_source="gnss")
    assert int(on_gnss.fixes["alt_invalidated"].sum()) == 5


def test_no_altitude_rule_ever_deletes_a_fix():
    # The invariant of tab:cleaning, on a flight where every altitude is impossible.
    flight = _glide()
    flight["alt"] = 99_000.0
    out = _clean(flight)
    assert len(out.fixes) == 300
    assert out.removed.empty
    assert out.fixes["alt_invalidated"].all()


# --------------------------------------------------------------------------------
# The integrity gate (applied after trimming)
# --------------------------------------------------------------------------------


def test_the_integrity_gate_counts_only_the_airborne_window():
    # Defects in a ground phase that trimming removes anyway must not condemn a flight.
    flight = _glide(n=300)
    flight.loc[0:40, "alt"] = 99_000.0  # 41 impossible altitudes, all before take-off
    out = _clean(flight)

    whole, whole_reason = integrity_gate(out, 0.0, 299.0, FIX)
    assert whole == pytest.approx(41 / 300)
    assert whole_reason == DROP_INTEGRITY

    airborne, airborne_reason = integrity_gate(out, 60.0, 299.0, FIX)
    assert airborne == 0.0
    assert airborne_reason is None


def test_the_integrity_gate_ignores_merged_duplicates():
    # A genuine 2 Hz logger records too well, not too badly: merging its duplicate
    # seconds must not read as the cleaning having rebuilt half the flight.
    flight = _glide(n=100)
    doubled = pd.concat([flight, flight], ignore_index=True).sort_values("t")
    out = _clean(doubled.reset_index(drop=True))

    assert out.report.n_merged_duplicates == 100
    fraction, reason = integrity_gate(out, 0.0, 99.0, FIX)
    assert fraction == 0.0
    assert reason is None


def test_a_missing_column_or_unknown_discipline_is_reported():
    flight = _glide(n=10)
    with pytest.raises(ValueError, match="alt"):
        clean_flight(flight.drop(columns=["alt"]), FIX, discipline="paragliders")
    with pytest.raises(ValueError, match="sailplanes"):
        clean_flight(flight, FIX, discipline="sailplanes")


def test_a_flagged_first_fix_that_is_reachable_is_kept():
    # The corroboration still rules: anomalous but possible means kept, at the start of
    # a track exactly as in the middle of one.
    flight = _glide(n=40, dt=10.0)
    flight.loc[0, "lat"] += 30.0 / _M_PER_DEG_LAT
    out = _clean(flight)

    assert out.report.n_removed_spike == 0
    assert len(out.fixes) == 40


def test_a_short_offset_is_removed_as_an_excursion_and_that_is_the_limit():
    # The rule parts the two cases at max_speed * block_span, ~900 m here: below it the
    # new branch is reachable from the anchor before the block expires, so the fixes in
    # between are removed as an excursion instead of the step being split. It is a real
    # limit of the impossibility gate and a bounded one -- at most one block of genuine
    # fixes, at a discontinuity -- and it is recorded here rather than left to be
    # rediscovered.
    flight = _glide()
    flight.loc[150:, "lat"] += 400.0 / _M_PER_DEG_LAT
    out = _clean(flight)

    assert out.report.n_splits == 0
    assert 0 < out.report.n_removed_spike <= 20


def test_a_run_of_null_island_fixes_is_removed_despite_the_broken_median():
    # The case the archive actually holds: a logger writes (0, 0) for a stretch. Once
    # such fixes are more than half of a Hampel window the median moves onto them, they
    # score a residual of zero and go unflagged -- it is the good fixes around them that
    # get flagged. A rule that required the flag would keep a 5000 km step; the
    # impossibility gate has no local scale in it and removes the run.
    flight = _glide()
    for start, stop in ((140, 152), (160, 172)):  # 24 of a 41-fix window: past half
        flight.loc[start : stop - 1, ["lat", "lon"]] = 0.0
    flags = hampel_flags(
        flight["t"].to_numpy(),
        flight["lat"].to_numpy(),
        flight["lon"].to_numpy(),
        FIX,
    )
    zeros = (flight["lat"] == 0.0).to_numpy() & (flight["lon"] == 0.0).to_numpy()
    assert int(zeros.sum()) == 24
    assert int((flags & zeros).sum()) == 16  # eight escape the broken median
    out = _clean(flight)

    assert out.report.n_removed_spike == 24  # every one of them goes anyway
    assert not ((out.fixes["lat"] == 0.0) & (out.fixes["lon"] == 0.0)).any()


def test_no_impossible_step_survives_between_two_kept_fixes():
    # The postcondition, on the case that produced it: a corrupt block the scan can
    # neither rejoin nor explain is kept, and the step back out of it is a 40 km jump in
    # one second. Left unmarked it would sit *inside* a segment and carry every average
    # taken over it.
    flight = _glide(n=400)
    flight.loc[150:190, "lat"] += 40_000.0 / _M_PER_DEG_LAT  # a 41 s excursion, capped
    out = _clean(flight)

    kept = out.fixes
    step = great_circle_m(
        kept["lat"].to_numpy()[:-1],
        kept["lon"].to_numpy()[:-1],
        kept["lat"].to_numpy()[1:],
        kept["lon"].to_numpy()[1:],
    )
    speed = step / np.diff(kept["t"].to_numpy())
    crossing = kept["split_before"].to_numpy()[1:]
    # Every surviving impossible step is a declared boundary, so no segment holds one.
    assert not (speed > FIX.max_horizontal_speed_mps["paragliders"])[~crossing].any()
    assert crossing.sum() >= 2  # into the block and back out of it


def test_the_postcondition_survives_a_later_deletion_pass():
    # It has to be applied after *every* pass that deletes, not inside the position
    # scan: the frozen-lock pass runs next and its removals create adjacencies the scan
    # never saw, one of which can be an impossible step no rule has declared a boundary.
    flight = _with_frozen_run(length=90)
    flight.loc[192, "lat"] += 3000.0 / _M_PER_DEG_LAT  # a jump just past the freeze
    out = _clean(flight)

    kept = out.fixes
    step = great_circle_m(
        kept["lat"].to_numpy()[:-1],
        kept["lon"].to_numpy()[:-1],
        kept["lat"].to_numpy()[1:],
        kept["lon"].to_numpy()[1:],
    )
    speed = step / np.diff(kept["t"].to_numpy())
    interior = ~kept["split_before"].to_numpy()[1:]
    assert not (speed > FIX.max_horizontal_speed_mps["paragliders"])[interior].any()


def test_a_track_crossing_the_antimeridian_is_not_read_as_motionless():
    # Three detectors read longitude componentwise, and every one of them is wrong on a
    # track written +179.99 then -179.99. The failure is not the obvious one: the
    # great-circle distance is *correctly* wrap-aware, so the two numerical extremes of
    # a straddling bounding box read as metres apart and a wing at 12 m/s looks
    # collapsed -- the frozen-lock rule firing on genuine motion.
    n = 400
    step_deg = 12.0 / (_M_PER_DEG_LAT * np.cos(np.radians(-20.0)))
    lon = ((179.99 + np.arange(n) * step_deg + 180.0) % 360.0) - 180.0
    flight = pd.DataFrame(
        {
            "t": np.arange(n, dtype=float),
            "lat": np.full(n, -20.0),
            "lon": lon,
            "alt": 1500.0 + np.arange(n, dtype=float),
            "valid": np.full(n, True),
        }
    )
    assert (np.abs(np.diff(lon)) > 1.0).any()  # the raw column really does jump

    out = clean_flight(flight, FIX, discipline="paragliders", alt_source="baro")
    assert out.report.n_removed_frozen == 0
    assert out.report.n_removed_spike == 0
    assert len(out.fixes) == n
    # The stored coordinate comes back on the convention every reader expects.
    assert out.fixes["lon"].between(-180.0, 180.0).all()


def test_the_duplicate_centroid_survives_the_antimeridian():
    # The componentwise mean fails the other way: halfway between +179.99 and -179.99 is
    # longitude zero, the null island -- the very artefact the cleaning removes.
    flight = pd.DataFrame(
        {
            "t": [0.0, 1.0, 1.0, 2.0],
            "lat": [-20.0] * 4,
            "lon": [179.99990, 179.99999, -179.99999, -179.99990],
            "alt": [1500.0] * 4,
            "valid": [True] * 4,
        }
    )
    out = clean_flight(flight, FIX, discipline="paragliders", alt_source="baro")
    merged = out.fixes.loc[out.fixes["t"] == 1.0, "lon"].item()
    assert abs(abs(merged) - 180.0) < 0.001  # on the meridian, not at zero


def test_an_early_spike_deletes_the_spike_and_not_the_good_fixes_before_it():
    """The other end of the same impossible step, and the reason the rule waits.

    An impossible step near the start says nothing about *which* of its two ends is the
    corrupt one. The first version of this rule fired on the step alone and always
    accused the earlier end, so an ordinary GPS spike a few seconds in had the good
    fixes deleted and the spike kept -- and the spike, being the survivor, became the
    origin of the local frame, 4 km from where the flight actually began. The rule now
    acts on the scan's *verdict* instead: only where removing what follows cannot
    restore the trend does the prefix become the accused.
    """
    for spike_at in (1, 3, 8, 15):
        flight = _glide()
        first = flight.loc[0, ["lat", "lon"]].to_numpy()
        flight.loc[spike_at, "lat"] += 4000.0 / 111_320.0
        out = _clean(flight)

        assert out.report.n_removed_spike == 1, f"spike at {spike_at}: not one deletion"
        assert out.report.n_splits == 0, (
            f"spike at {spike_at}: split instead of removal"
        )
        assert out.fixes["t"].iloc[0] == 0.0, (
            f"spike at {spike_at}: lost the true start"
        )
        assert out.fixes.loc[
            out.fixes.index[0], ["lat", "lon"]
        ].to_numpy() == pytest.approx(first)


def test_an_unreturned_vertical_step_is_counted_even_though_no_rule_censors_it():
    """The third shape of super-threshold vertical step, which matched no rule.

    `_clean_altitude` recognised an out-and-back spike and a coherent run. A single
    step that is never undone -- a barometric re-reference -- is neither, so it was
    censored by nothing *and counted by nothing*, and the smoothing differentiated
    it into a vertical velocity of up to 5117 m/s in the written table. On a sample
    of the archive 8.3 % of paraglider flights carry at least one. Counting it is
    the part that is not a design decision; what to do about it is, and is left
    open.
    """
    flight = _glide()
    n = len(flight)
    flight.loc[n // 2 :, "alt"] += 400.0  # the reference changed, and stays changed

    out = _clean(flight)
    assert out.report.n_alt_level_shift == 1
    # And the two rules that existed before it still see nothing, which is the point.
    assert out.report.n_alt_vz_spike == 0
    assert out.report.n_vz_runs == 0

    # An out-and-back spike of the same size is still the *other* case, not this one.
    other = _glide()
    other.loc[n // 2, "alt"] += 400.0
    spiked = _clean(other)
    assert spiked.report.n_alt_level_shift == 0
    assert spiked.report.n_alt_vz_spike == 1


def test_a_corrupt_fix_at_the_very_end_is_deleted_not_split_at():
    """The mirror of the opening-block rule, and it saves the whole flight.

    A block still open when the track ends never rejoins, because there is nothing after
    it to rejoin with. Split-marking it keeps the fix, which then becomes the farthest
    point from the origin -- and the reach bound of sec:flightfilter refuses the flight
    whole. One corrupt trailing fix discarded four thousand seconds of perfect flight.
    A block still pending at the end is bounded by `block_span_s` by construction, so
    deleting it costs at most those seconds, near a landing the trimming would very
    likely take anyway.
    """
    flight = _glide(n=300)
    flight.loc[299, ["lat", "lon"]] = 0.0  # the null island, on the last fix only

    out = _clean(flight)
    assert out.report.n_removed_spike == 1
    assert out.report.n_splits == 0
    assert len(out.fixes) == 299
    assert not ((out.fixes["lat"] == 0.0) & (out.fixes["lon"] == 0.0)).any()


def test_a_flight_with_one_corrupt_trailing_fix_survives_the_pipeline():
    # End to end, because the cost of getting this wrong was paid at the flight level:
    # the corrupt fix passed cleaning, became the extent, and the reach bound dropped
    # the flight.
    from soaring.analysis.preproc.pipeline import run_flight

    n = 5000
    t = np.arange(n, dtype=float)
    east = 11.0 * t + 250.0 * np.sin(2 * np.pi * t / 700.0)
    north = 180.0 * np.sin(2 * np.pi * t / 430.0) + 3.0 * t
    alt = 1400.0 + 500.0 * (1.0 - np.cos(2 * np.pi * t / 900.0))
    ground = 120
    for channel in (east, north, alt):
        channel[:ground] = channel[ground]
        channel[-ground:] = channel[-ground - 1]
    track = pd.DataFrame(
        {
            "t": t,
            "lat": LAT0 + north / _M_PER_DEG_LAT,
            "lon": LON0 + east / _M_PER_DEG_LON,
            "valid": True,
            "baro_alt": np.round(alt),
            "gnss_alt": np.round(alt + 47.0),
        }
    )
    track.loc[n - 1, ["lat", "lon"]] = 0.0

    result = run_flight(
        track,
        load_preproc_config(),
        source="paraglider",
        flight_id="tail",
        discipline="paragliders",
    )
    assert result.kept, f"dropped: {result.meta.drop_reason}"
    assert result.meta.extent_km < 100.0


def test_corruption_at_the_very_start_is_split_off_and_the_flight_is_refused():
    """No rule attributes an impossible step at the start, and that is deliberate.

    The first fix of the trimmed track becomes the origin of the local frame
    (sec:enu), so a corrupt one displaces every coordinate of the flight. Two rules
    were written to delete the corrupt prefix and both were wrong, in opposite
    directions: one accused the earlier end always, so an ordinary spike three
    seconds in deleted the good fixes and promoted the spike to origin; the other
    acted on the scan's split, whose index is the first fix of the block that could
    not be rejoined -- which lies *after* the step whenever the corruption outlasts
    `block_span_s`, so a 50 s corrupt run five seconds in deleted five good fixes
    and kept fifty bad ones, origin 5039 km out.

    A discontinuity is therefore left as a discontinuity, and the guarantee is taken
    where it can be stated without attribution: at the flight level.
    """
    from soaring.analysis.preproc.pipeline import run_flight

    n = 5000
    t = np.arange(n, dtype=float)
    east = 11.0 * t + 250.0 * np.sin(2 * np.pi * t / 700.0)
    north = 180.0 * np.sin(2 * np.pi * t / 430.0) + 3.0 * t
    alt = 1400.0 + 500.0 * (1.0 - np.cos(2 * np.pi * t / 900.0))
    for channel in (east, north, alt):
        channel[:120] = channel[120]
        channel[-120:] = channel[-121]

    for corrupt_until in (3, 25, 55):  # inside `w`, just past it, well past it
        track = pd.DataFrame(
            {
                "t": t,
                "lat": LAT0 + north / _M_PER_DEG_LAT,
                "lon": LON0 + east / _M_PER_DEG_LON,
                "valid": True,
                "baro_alt": np.round(alt),
                "gnss_alt": np.round(alt + 47.0),
            }
        )
        track.loc[: corrupt_until - 1, ["lat", "lon"]] = 0.0
        result = run_flight(
            track,
            load_preproc_config(),
            source="paraglider",
            flight_id=f"lead{corrupt_until}",
            discipline="paragliders",
        )
        assert not result.kept, f"{corrupt_until} corrupt fixes: kept anyway"
        assert result.meta.drop_reason == "extent_out_of_reach_of_the_first_fix"

    # And the case the withdrawn rules got backwards -- good fixes, then an early
    # spike -- is handled by the ordinary bounded removal, true origin preserved.
    clean = _glide(n=300)
    truth = clean.loc[0, ["lat", "lon"]].to_numpy()
    clean.loc[3, "lat"] += 4000.0 / _M_PER_DEG_LAT
    out = _clean(clean)
    assert out.report.n_removed_spike == 1
    assert out.report.n_splits == 0
    assert out.fixes.loc[
        out.fixes.index[0], ["lat", "lon"]
    ].to_numpy() == pytest.approx(truth)


def test_the_largest_boundary_jump_is_reported():
    """What a split leaves in the absolute position: bounded, not repaired.

    Segments keep the parent's origin, so everything after a re-acquisition offset
    carries an unknown constant -- which enters the ensemble MSD, built from
    absolute position, and not the time-averaged one, built from increments. No rule
    acts on it, because on the archive the median such displacement is tens of
    metres; what is needed is the number, so the claim can be checked instead of
    asserted.
    """
    plain = _clean(_glide())
    assert plain.report.split_jump_max_m == 0.0

    flight = _glide()
    flight.loc[150:, "lat"] += 4000.0 / _M_PER_DEG_LAT  # the track jumps and stays
    out = _clean(flight)
    assert out.report.n_splits == 1
    assert out.report.split_jump_max_m == pytest.approx(4000.0, rel=0.02)
