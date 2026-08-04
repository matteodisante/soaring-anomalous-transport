import numpy as np
import pandas as pd
import pytest

from soaring.analysis.preproc.resample import (
    DROP_INCOMPLETE,
    DROP_NO_CADENCE,
    DROP_NO_SEGMENT,
    DROP_TOO_SHORT,
    DROP_TOO_SPARSE,
    FIX_COLUMNS,
    SEGMENT_COLUMNS,
    resample_flight,
    segment_bounds,
    split_bound_s,
)
from soaring.analysis.config import (
    SamplingThresholds,
    load_preproc_config,
)

# The adopted values, restated here so the behaviour tests below read as behaviour and
# not as a second copy of the config; test_split_bound_uses_the_adopted_config pins them
# to configs/preprocessing.yaml.
SAMPLING = SamplingThresholds(
    max_gap_factor=10.0,
    max_gap_seconds=20.0,
    max_missing_fraction=0.10,
    min_segment_duration_s=90.0,
)


def _straight_flight(duration_s=600.0, dt=1.0, *, v_e=10.0, v_n=5.0, climb=2.0):
    """A flight whose every coordinate is exactly linear in time.

    The point of a straight track is that both interpolants reproduce it *exactly* --
    a monotone cubic and a chord agree on a straight line -- so anything the resampling
    fills in has a known right answer to the last bit.
    """
    t = np.arange(0.0, duration_s + dt, dt)
    return pd.DataFrame({"t": t, "E": v_e * t, "N": v_n * t, "z": 1000.0 + climb * t})


def _drop_times(flight, times):
    """Remove the fixes at these times (a logger drop-out, or a cleaning deletion)."""
    keep = ~np.isin(flight["t"].to_numpy(), np.asarray(times, dtype=float))
    return flight[keep].reset_index(drop=True)


# --------------------------------------------------------------------------------
# The split bound (sec:uniform, "The split bound has two scales")
# --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dt", "expected", "binding_term"),
    [
        (1.0, 10.0, "relative 10 dt"),
        (2.0, 20.0, "absolute cap"),
        (5.0, 20.0, "absolute cap"),
        (10.0, 20.0, "absolute cap"),
        (15.0, 30.0, "2 dt floor"),
        (30.0, 60.0, "2 dt floor"),
    ],
)
def test_split_bound_binds_where_the_thesis_says(dt, expected, binding_term):
    # sec:uniform: the relative bound at the dominant 1 s cadence, the absolute cap from
    # 2 s to 10 s, the 2 dt floor above that. `binding_term` names it for the reader.
    assert float(split_bound_s(dt, SAMPLING)) == pytest.approx(expected)


def test_split_bound_never_splits_on_a_single_missed_fix():
    # The first of the three constraints, at *every* cadence: this is what the 2 dt
    # floor is for, and it is why the cap is not simply min(10 dt, 20 s).
    dt = np.array([0.5, 1.0, 2.0, 5.0, 10.0, 12.0, 20.0, 60.0])
    assert np.all(split_bound_s(dt, SAMPLING) >= 2.0 * dt)


def test_split_bound_uses_the_adopted_config():
    sampling = load_preproc_config().sampling
    assert float(split_bound_s(1.0, sampling)) == pytest.approx(10.0)
    assert float(split_bound_s(5.0, sampling)) == pytest.approx(20.0)


# --------------------------------------------------------------------------------
# Where the cuts fall
# --------------------------------------------------------------------------------


def test_segment_bounds_without_a_gap_is_one_segment():
    assert segment_bounds(np.arange(10.0), 10.0) == [(0, 10)]


def test_segment_bounds_cuts_at_a_long_gap_only():
    t = np.array([0.0, 1.0, 2.0, 30.0, 31.0])
    assert segment_bounds(t, 10.0) == [(0, 3), (3, 5)]
    # A gap of exactly g_max is bridged, not cut: the rule is "longer than g_max".
    assert segment_bounds(np.array([0.0, 1.0, 11.0, 12.0]), 10.0) == [(0, 4)]
    assert segment_bounds(np.array([0.0, 1.0, 11.01, 12.0]), 10.0) == [(0, 2), (2, 4)]


def test_segment_bounds_honours_a_forced_split():
    # A re-acquisition offset: the track jumps and stays, with no time gap at all. Only
    # the transition is unknown, so it is handled exactly like a long gap (sec:uniform).
    t = np.arange(6.0)
    forced = np.array([False, False, False, True, False, False])
    assert segment_bounds(t, 10.0, forced=forced) == [(0, 3), (3, 6)]


# --------------------------------------------------------------------------------
# The uniform case, and the short holes
# --------------------------------------------------------------------------------


def test_a_uniform_flight_passes_through_unchanged():
    flight = _straight_flight()
    out = resample_flight(flight, SAMPLING)

    assert out.drop_reason is None
    assert out.dt_s == pytest.approx(1.0)
    assert out.g_max_s == pytest.approx(10.0)
    assert list(out.fixes.columns) == FIX_COLUMNS
    assert len(out.fixes) == len(flight)
    assert out.fixes["t"].to_numpy() == pytest.approx(flight["t"].to_numpy())
    assert out.fixes["E"].to_numpy() == pytest.approx(flight["E"].to_numpy())
    assert out.fixes["z"].to_numpy() == pytest.approx(flight["z"].to_numpy())
    # "Uniform as recorded": nothing was reconstructed, so nothing is flagged.
    assert not out.fixes["interpolated"].any()
    assert out.frac_interpolated == 0.0
    assert out.was_resampled is False
    assert out.fixes["segment_id"].unique().tolist() == [0]


def test_a_single_dropped_fix_is_bridged_exactly():
    flight = _straight_flight()
    holed = _drop_times(flight, [100.0])
    out = resample_flight(holed, SAMPLING)

    assert len(out.segments) == 1  # a 2 s hole is far below g_max = 10 s
    assert out.fixes["interpolated"].sum() == 1
    assert out.fixes.loc[out.fixes["t"] == 100.0, "interpolated"].item() is True
    assert out.was_resampled is True
    # The filled point is *exact*: the track is straight, and neither interpolant
    # invents anything on a straight line.
    assert out.fixes["E"].to_numpy() == pytest.approx(flight["E"].to_numpy())
    assert out.fixes["N"].to_numpy() == pytest.approx(flight["N"].to_numpy())
    assert out.fixes["z"].to_numpy() == pytest.approx(flight["z"].to_numpy())
    assert out.frac_interpolated == pytest.approx(1.0 / 601.0)


def test_a_gap_of_exactly_g_max_is_bridged_and_caps_the_filled_points():
    # sec:uniform: the relative part of the bound "caps the number of interpolated grid
    # points at ten". At the 1 s cadence g_max is 10 s, so the widest bridged hole
    # leaves nine reconstructed points between two measured ones.
    flight = _straight_flight()
    holed = _drop_times(flight, np.arange(101.0, 110.0))
    out = resample_flight(holed, SAMPLING)

    assert len(out.segments) == 1
    assert out.fixes["interpolated"].sum() == 9
    assert out.fixes["E"].to_numpy() == pytest.approx(flight["E"].to_numpy())


def test_a_gap_past_g_max_splits_instead_of_bridging():
    flight = _straight_flight()
    holed = _drop_times(flight, np.arange(101.0, 111.0))  # an 11 s hole > g_max
    out = resample_flight(holed, SAMPLING)

    assert len(out.segments) == 2
    assert out.segments["kept"].tolist() == [True, True]
    # Nothing was fabricated inside the hole: no fix carries a time strictly inside it.
    inside = (out.fixes["t"] > 100.0) & (out.fixes["t"] < 111.0)
    assert not inside.any()
    assert not out.fixes["interpolated"].any()


# --------------------------------------------------------------------------------
# What a split means (sec:uniform, "Consequences of a split")
# --------------------------------------------------------------------------------


def test_a_segment_keeps_the_parent_clock_and_origin():
    # The single easiest thing to get wrong: a segment is an observation window onto a
    # process already t0 old, not a fresh flight starting at t = 0.
    flight = _straight_flight()
    holed = _drop_times(flight, np.arange(201.0, 251.0))
    out = resample_flight(holed, SAMPLING)

    second = out.fixes[out.fixes["segment_id"] == 1]
    assert second["t"].iloc[0] == pytest.approx(251.0)  # NOT re-zeroed
    # ...and the coordinates are still the parent's: E is 10 m/s times the parent clock.
    assert second["E"].iloc[0] == pytest.approx(2510.0)
    assert out.segments.loc[1, "t_start"] == pytest.approx(251.0)


def test_split_boundaries_are_flagged_censored_and_flight_ends_are_not():
    flight = _straight_flight()
    holed = _drop_times(flight, np.arange(201.0, 251.0))
    out = resample_flight(holed, SAMPLING)

    assert list(out.segments.columns) == SEGMENT_COLUMNS
    # Only the two boundaries the split created truncate a phase in progress; the
    # flight's own first and last boundary are a different thing and stay False.
    assert out.segments["censored_start"].tolist() == [False, True]
    assert out.segments["censored_end"].tolist() == [True, False]


def test_a_short_segment_is_dropped_alone_not_the_flight():
    # No second pass of the flight-level cuts: only the minimal segment gate applies,
    # and it removes the offending segment, never its parent (sec:uniform).
    flight = _straight_flight()
    holed = flight[(flight["t"] <= 300.0) | (flight["t"] >= 360.0)]
    holed = holed[holed["t"] <= 420.0].reset_index(drop=True)  # a 60 s tail < 90 s
    out = resample_flight(holed, SAMPLING)

    assert out.drop_reason is None
    assert out.segments["kept"].tolist() == [True, False]
    assert out.segments["drop_reason"].isna().tolist() == [True, False]
    assert out.segments.loc[1, "drop_reason"] == DROP_TOO_SHORT
    assert out.fixes["segment_id"].unique().tolist() == [0]
    # The dropped segment is still on the record, with its raw fix count and window.
    assert out.segments.loc[1, "n_fix_raw"] == 61
    assert out.segments.loc[1, "n_fix"] == 0


def test_a_sparse_segment_is_dropped_and_takes_the_flight_only_if_it_is_alone():
    # A flight riddled with isolated drop-outs -- none of them wide enough to split, but
    # 13 % of the grid unsupported, past the 10 % cap. One segment, so the flight goes
    # with it, and the reason is recorded at both levels.
    flight = _straight_flight(duration_s=300.0)
    out = resample_flight(_drop_times(flight, np.arange(5.0, 285.0, 7.0)), SAMPLING)

    assert len(out.segments) == 1
    assert out.segments.loc[0, "frac_interpolated"] > 0.10
    assert out.segments.loc[0, "drop_reason"] == DROP_TOO_SPARSE
    assert out.drop_reason == DROP_NO_SEGMENT
    assert out.fixes.empty
    assert out.fixes["interpolated"].dtype == bool  # dtypes survive an empty result


def test_the_missing_fraction_is_judged_per_segment_not_per_flight():
    # The check runs after splitting on purpose: a single long gap, which will not be
    # interpolated at all, must not condemn a flight whose segments are each perfectly
    # sampled (sec:uniform). Pre-split this flight is 25 % "missing"; per segment, 0 %.
    flight = _straight_flight(duration_s=800.0)
    holed = flight[(flight["t"] <= 300.0) | (flight["t"] >= 500.0)].reset_index(
        drop=True
    )
    out = resample_flight(holed, SAMPLING)

    assert out.segments["kept"].tolist() == [True, True]
    assert out.segments["frac_interpolated"].tolist() == [0.0, 0.0]
    assert out.frac_interpolated == 0.0


# --------------------------------------------------------------------------------
# Per-channel fill: monotone cubic on the horizontal, linear on the altitude
# --------------------------------------------------------------------------------


def test_the_altitude_is_filled_linearly_and_the_horizontal_is_not():
    # The deliberate asymmetry of sec:uniform, made visible on a curved track: over a
    # hole, a chord through the neighbours misses a curved signal by |z''| dt^2 / ...,
    # while the monotone cubic follows the curvature. z takes the chord -- the estimator
    # that cannot overshoot -- because it is differentiated once more, into the
    # segmentation's discriminant, before anything else reads it.
    t = np.arange(0.0, 200.0)
    curved = 0.5 * t**2
    flight = pd.DataFrame({"t": t, "E": curved, "N": curved, "z": 1000.0 + curved})
    out = resample_flight(_drop_times(flight, [100.0]), SAMPLING)

    filled = out.fixes[out.fixes["t"] == 100.0]
    chord = 0.5 * (curved[99] + curved[101])  # what linear interpolation must give
    assert filled["z"].item() - 1000.0 == pytest.approx(chord)
    assert filled["z"].item() - 1000.0 - curved[100] == pytest.approx(0.5)  # z'' dt^2/2
    # The monotone cubic follows the curvature instead: several times closer.
    assert abs(filled["E"].item() - curved[100]) < 0.2 * abs(chord - curved[100])


def test_the_horizontal_fill_never_overshoots_its_neighbours():
    # A launch from rest: flat, then a sharp linear run. An unconstrained cubic spline
    # would dip below the flat stretch here; a monotone piecewise cubic cannot, and that
    # is the whole reason for choosing it -- an excursion is indistinguishable, to the
    # smoothing, from a real manoeuvre (sec:uniform).
    t = np.arange(0.0, 200.0)
    ramp = np.where(t < 100.0, 0.0, 10.0 * (t - 100.0))
    flight = pd.DataFrame({"t": t, "E": ramp, "N": ramp, "z": np.full(t.size, 1000.0)})
    out = resample_flight(_drop_times(flight, [102.0]), SAMPLING)

    filled = out.fixes[out.fixes["t"] == 102.0]["E"].item()
    assert ramp[101] <= filled <= ramp[103]
    assert float(out.fixes["E"].min()) >= 0.0  # no dip below the flat stretch


def test_an_altitude_dropped_at_cleaning_is_restored_here():
    # sec:uniform: the fill is per channel. A fix whose barometric spike stage (ii)
    # invalidated keeps its position and gets its altitude back on the grid -- and the
    # grid point stays *measured*, because a fix does support it; what marks the
    # restoration is the cleaning flag the fix carries, not the interpolated column.
    flight = _straight_flight(duration_s=200.0)
    flight.loc[flight["t"] == 100.0, "z"] = np.nan
    flight["z_invalidated"] = flight["t"] == 100.0
    out = resample_flight(flight, SAMPLING)

    at_hole = out.fixes[out.fixes["t"] == 100.0]
    assert at_hole["z"].item() == pytest.approx(1200.0)  # 1000 + 2 m/s * 100 s
    assert at_hole["interpolated"].item() is False
    assert at_hole["z_invalidated"].item() is True
    assert np.all(np.isfinite(out.fixes["z"].to_numpy()))  # the completeness invariant


def test_carried_flags_follow_the_nearest_fix_and_blank_where_reconstructed():
    flight = _straight_flight(duration_s=200.0)
    flight["hampel_flagged"] = flight["t"] == 50.0
    out = resample_flight(_drop_times(flight, [100.0]), SAMPLING)

    assert out.fixes.loc[out.fixes["t"] == 50.0, "hampel_flagged"].item() is True
    assert out.fixes["hampel_flagged"].sum() == 1
    # A reconstructed grid point carries no measurement, so it carries no flag either.
    assert out.fixes.loc[out.fixes["t"] == 100.0, "hampel_flagged"].item() is False


def test_a_forced_split_column_cuts_without_a_time_gap():
    flight = _straight_flight(duration_s=400.0)
    flight["split_before"] = flight["t"] == 200.0
    out = resample_flight(flight, SAMPLING)

    assert out.segments["kept"].tolist() == [True, True]
    assert out.segments["t_start"].tolist() == [0.0, 200.0]
    assert out.segments["censored_end"].tolist() == [True, False]
    # The marker itself is consumed by this stage, not carried into the fixes table.
    assert "split_before" not in out.fixes.columns


# --------------------------------------------------------------------------------
# Refusals and degenerate input
# --------------------------------------------------------------------------------


def test_a_flight_without_a_cadence_is_dropped_with_a_reason():
    one_fix = _straight_flight(duration_s=0.0)
    out = resample_flight(one_fix, SAMPLING)
    assert out.drop_reason == DROP_NO_CADENCE
    assert out.fixes.empty
    assert out.segments.empty


def test_backward_or_duplicate_timestamps_are_refused():
    # Time-base defects belong to stage (ii)'s structural rules; absorbing them here
    # would hide them.
    flight = _straight_flight(duration_s=200.0)
    flight.loc[10, "t"] = flight.loc[9, "t"]
    with pytest.raises(ValueError, match="strictly increasing"):
        resample_flight(flight, SAMPLING)


def test_a_missing_local_frame_column_is_reported():
    flight = _straight_flight(duration_s=200.0).drop(columns=["z"])
    with pytest.raises(ValueError, match=r"\['z'\]"):
        resample_flight(flight, SAMPLING)


def test_a_segment_whose_channel_cannot_be_filled_is_dropped():
    # The completeness invariant of sec:uniform is a promise to everything downstream:
    # within a retained segment every grid time carries a defined (E, N, z). A channel
    # with nothing to interpolate between cannot keep it, so the segment goes.
    flight = _straight_flight(duration_s=200.0)
    flight["z"] = np.nan
    out = resample_flight(flight, SAMPLING)

    assert out.segments.loc[0, "drop_reason"] == DROP_INCOMPLETE
    assert out.drop_reason == DROP_NO_SEGMENT
    assert out.fixes.empty


def test_a_reconstructed_altitude_is_recorded_as_such():
    """`interpolated` is a statement about the time base, and z can be absent alone.

    A logger that writes no barometric value, or a cleaning that removes one, leaves a
    hole in the vertical channel while the horizontal record is intact: no time gap
    opens, so every grid point is `measured` and `interpolated` stays False, while the
    linear bridge fills the hole with a straight line of unbounded length. On a flight
    missing 500 s of altitude the z error reached 540 m and the smoothing turned the
    straight line into a vertical velocity that was pure invention -- with
    `frac_interpolated` at 0.00000 and `was_resampled` at False. The vertical therefore
    carries its own flag.
    """
    n, dt = 400, 1.0
    t = np.arange(n, dtype=float) * dt
    local = pd.DataFrame(
        {
            "t": t,
            "E": 12.0 * t,
            "N": 3.0 * t,
            "z": 1000.0 + 2.0 * t,
            "split_before": False,
        }
    )
    local.loc[100:199, "z"] = np.nan  # 100 s the logger never wrote
    out = resample_flight(local, SAMPLING)

    fixes = out.fixes
    assert not fixes["interpolated"].any(), "no time gap opened, so nothing is that"
    reconstructed = fixes["z_reconstructed"].to_numpy(dtype=bool)
    assert reconstructed.sum() == 100
    assert reconstructed[100:200].all()
    assert not reconstructed[:100].any() and not reconstructed[200:].any()

    assert out.frac_z_reconstructed == pytest.approx(0.25)
    assert out.z_gap_max_s == pytest.approx(100.0)
    assert out.segments.loc[0, "frac_z_reconstructed"] == pytest.approx(0.25)
    # And the two fractions are independent statements, which is the whole point.
    assert out.frac_interpolated == 0.0


def test_the_worst_altitude_run_separates_many_small_holes_from_one_long_one():
    # A fraction cannot tell them apart, and they are not the same defect: a linear
    # bridge over two seconds is a repair, over twelve minutes it is an invention.
    n = 400
    t = np.arange(n, dtype=float)
    base = pd.DataFrame(
        {"t": t, "E": 12.0 * t, "N": 3.0 * t, "z": 1000.0 + 2.0 * t}
    ).assign(split_before=False)

    scattered = base.copy()
    for start in range(20, 220, 20):
        scattered.loc[start : start + 4, "z"] = np.nan  # 10 holes of five seconds
    one_long = base.copy()
    one_long.loc[100:149, "z"] = np.nan  # one hole of fifty

    a, b = resample_flight(scattered, SAMPLING), resample_flight(one_long, SAMPLING)
    assert a.frac_z_reconstructed == pytest.approx(b.frac_z_reconstructed)
    assert a.z_gap_max_s == pytest.approx(5.0)
    assert b.z_gap_max_s == pytest.approx(50.0)
