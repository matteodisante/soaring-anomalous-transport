import numpy as np
import pandas as pd
import pytest

from soaring.analysis.preproc.flightfilter import (
    DROP_FLAT,
    DROP_SHORT_PATH,
    DROP_TOO_LONG,
    DROP_TOO_SHORT,
    filter_flight,
    flight_quantities,
)
from soaring.analysis.preproc.trimming import (
    DROP_NO_FLIGHT,
    airborne_window,
    trim_flight,
)
from soaring.analysis.config import load_preproc_config

CFG = load_preproc_config()
TRIM, FLIGHT = CFG.trimming, CFG.flight
SUSPECT_MIN_S = CFG.fix.frozen_tau_s
# What the frozen-lock rule already calls motionless, read as a rate: 5 m / 60 s.
MAX_DRIFT_MPS = CFG.fix.frozen_delta_z_m / CFG.fix.frozen_tau_s
LAT0, LON0 = 45.0, 7.0
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = _M_PER_DEG_LAT * np.cos(np.radians(LAT0))


def _from_speed(speed_mps, alt_mps=None, dt=1.0):
    """A flight built from a per-second ground speed and climb rate, flying due east."""
    speed = np.asarray(speed_mps, dtype=float)
    n = speed.size
    east = np.concatenate([[0.0], np.cumsum(speed[:-1] * dt)])
    climb = np.zeros(n) if alt_mps is None else np.asarray(alt_mps, dtype=float)
    return pd.DataFrame(
        {
            "t": np.arange(n) * dt,
            "lat": np.full(n, LAT0),
            "lon": LON0 + east / _M_PER_DEG_LON,
            "alt": 1000.0 + np.concatenate([[0.0], np.cumsum(climb[:-1] * dt)]),
            "split_before": np.zeros(n, dtype=bool),
        }
    )


# --------------------------------------------------------------------------------
# Outer ground phases
# --------------------------------------------------------------------------------


def test_take_off_and_landing_are_the_sustained_speed_rule():
    # 100 s on the ground, 400 s of flight, 100 s on the ground again.
    speed = np.concatenate([np.zeros(100), np.full(400, 12.0), np.zeros(100)])
    flight = _from_speed(speed)
    out = trim_flight(
        flight, TRIM, suspect_min_span_s=SUSPECT_MIN_S, max_drift_mps=MAX_DRIFT_MPS
    )

    assert out.drop_reason is None
    # Take-off is the first fix of the sustained-fast run, landing the last fix it
    # reaches: steps 100..499 are fast, so the airborne fixes are 100..500.
    assert out.t_on == pytest.approx(100.0)
    assert out.t_off == pytest.approx(500.0)
    assert len(out.fixes) == 401
    assert out.trimmed_fraction == pytest.approx(1.0 - 400.0 / 599.0, rel=1e-6)
    # The clock is re-zeroed at the first fix of free flight (sec:notation).
    assert out.fixes["t"].iloc[0] == 0.0
    assert out.fixes["t"].iloc[-1] == pytest.approx(400.0)


def test_a_brief_gust_on_the_ground_is_not_a_take_off():
    # The persistence T0 exists for exactly this: a few fast seconds among the ground
    # fixes must not be read as the flight starting there.
    speed = np.zeros(600)
    speed[50:55] = 20.0  # a 5 s gust, far short of T0 = 30 s
    speed[200:500] = 12.0
    out = trim_flight(
        _from_speed(speed),
        TRIM,
        suspect_min_span_s=SUSPECT_MIN_S,
        max_drift_mps=MAX_DRIFT_MPS,
    )

    assert out.t_on == pytest.approx(200.0)


def test_soaring_into_wind_does_not_end_the_flight():
    # Read forward, "the first sustained drop below v0" would cut here; read backward
    # from the end, the rule keeps the whole flight, which is the point of eq:trimming.
    speed = np.concatenate(
        [
            np.zeros(60),
            np.full(200, 12.0),
            np.full(300, 1.0),
            np.full(200, 12.0),
            np.zeros(60),
        ]
    )
    out = trim_flight(
        _from_speed(speed),
        TRIM,
        suspect_min_span_s=SUSPECT_MIN_S,
        max_drift_mps=MAX_DRIFT_MPS,
    )

    assert out.t_on == pytest.approx(60.0)
    assert out.t_off == pytest.approx(760.0)
    assert len(out.fixes) == 701  # the slow stretch in the middle is kept


def test_a_flight_that_never_flew_is_dropped_with_a_reason():
    out = trim_flight(
        _from_speed(np.zeros(600)),
        TRIM,
        suspect_min_span_s=SUSPECT_MIN_S,
        max_drift_mps=MAX_DRIFT_MPS,
    )
    assert out.drop_reason == DROP_NO_FLIGHT
    assert out.fixes.empty
    assert out.trimmed_fraction == 1.0


def test_airborne_window_needs_two_fixes():
    assert (
        airborne_window(np.array([0.0]), np.array([45.0]), np.array([7.0]), TRIM)
        is None
    )


# --------------------------------------------------------------------------------
# Interior ground stints
# --------------------------------------------------------------------------------


def _with_interior_stint(stint_s, climb_during=0.0):
    speed = np.concatenate(
        [
            np.zeros(60),
            np.full(600, 12.0),
            np.zeros(stint_s),
            np.full(600, 12.0),
            np.zeros(60),
        ]
    )
    climb = np.zeros(speed.size)
    climb[660 : 660 + stint_s] = climb_during
    return _from_speed(speed, alt_mps=climb)


def test_a_long_flat_interior_stint_is_excised_and_split():
    # A top-landing: 12 minutes at zero ground speed with a flat barometer.
    out = trim_flight(
        _with_interior_stint(720),
        TRIM,
        suspect_min_span_s=SUSPECT_MIN_S,
        max_drift_mps=MAX_DRIFT_MPS,
    )

    assert out.n_interior_excised == 1
    assert len(out.fixes) == 1200  # the stint's fixes are gone
    assert int(out.fixes["split_before"].sum()) == 1
    # The parts before and after are separate segments of the same parent flight: the
    # marker sits on the first fix that survives the excision, in the re-zeroed clock.
    boundary = out.fixes.loc[out.fixes["split_before"], "t"].item()
    assert boundary == pytest.approx(1321.0)
    assert not ((out.fixes["t"] > 600.0) & (out.fixes["t"] < 1320.0)).any()


def test_a_stint_where_the_wing_is_still_climbing_is_kept():
    # The independent-sensor argument again: a wing at zero ground speed in real air
    # still moves vertically, so the flatness condition is what separates a landing from
    # a wing parked in lift.
    out = trim_flight(
        _with_interior_stint(720, climb_during=1.0),
        TRIM,
        suspect_min_span_s=SUSPECT_MIN_S,
        max_drift_mps=MAX_DRIFT_MPS,
    )
    assert out.n_interior_excised == 0
    assert len(out.fixes) == 1921


def test_the_flatness_test_is_run_on_the_detrended_altitude():
    # The barometric reference wanders by tens of metres over an hour, which over
    # T_ground is already of the order of the tolerance. Testing the raw range would let
    # a perfectly stationary pilot fail on a pressure change alone.
    drifting = _with_interior_stint(720, climb_during=0.02)  # 14 m of drift over 720 s
    out = trim_flight(
        drifting, TRIM, suspect_min_span_s=SUSPECT_MIN_S, max_drift_mps=MAX_DRIFT_MPS
    )
    assert out.n_interior_excised == 1


def test_a_short_flat_stint_is_flagged_and_not_cut():
    out = trim_flight(
        _with_interior_stint(300),
        TRIM,
        suspect_min_span_s=SUSPECT_MIN_S,
        max_drift_mps=MAX_DRIFT_MPS,
    )

    assert out.n_interior_excised == 0
    assert len(out.suspect_intervals) == 1
    span = out.suspect_intervals.iloc[0]
    assert span["t_end"] - span["t_start"] == pytest.approx(300.0, abs=2.0)
    assert len(out.fixes) == 1501  # nothing removed


def test_stints_below_the_reporting_floor_are_not_even_flagged():
    # Every thermalling flight holds brief slow moments; a list that reported them all
    # would bury the mid-flight landings it exists to surface.
    out = trim_flight(
        _with_interior_stint(20),
        TRIM,
        suspect_min_span_s=SUSPECT_MIN_S,
        max_drift_mps=MAX_DRIFT_MPS,
    )
    assert out.suspect_intervals.empty


# --------------------------------------------------------------------------------
# Stage (iv): the whole-flight cuts
# --------------------------------------------------------------------------------


def _xc_flight(duration_s=3000.0, speed=12.0, alt_range=800.0):
    n = int(duration_s) + 1
    climb = np.full(n, alt_range / (duration_s / 2.0))
    climb[n // 2 :] *= -1.0
    return _from_speed(np.full(n, speed), alt_mps=climb)


def test_a_genuine_cross_country_flight_passes():
    verdict = filter_flight(_xc_flight(), FLIGHT)
    assert verdict.drop_reason is None
    assert verdict.duration_s == pytest.approx(3000.0)
    assert verdict.path_km == pytest.approx(36.0, rel=2e-3)
    assert verdict.alt_range_m == pytest.approx(800.0, rel=1e-3)


@pytest.mark.parametrize(
    ("flight", "expected"),
    [
        (_xc_flight(duration_s=1200.0), DROP_TOO_SHORT),  # 20 min: a sled run
        (_xc_flight(duration_s=70_000.0), DROP_TOO_LONG),  # a logger left running
        (_xc_flight(speed=5.5), DROP_SHORT_PATH),  # 16 km over 50 min
        (_xc_flight(alt_range=200.0), DROP_FLAT),  # not soaring
    ],
)
def test_each_cut_fires_on_its_own_defect(flight, expected):
    assert filter_flight(flight, FLIGHT).drop_reason == expected


def test_duration_and_path_are_never_summed_across_a_split():
    # A split marks an interval whose trajectory is unknown; a straight line drawn over
    # it must not be counted as flown, nor its duration as airborne.
    flight = _xc_flight()
    flight.loc[1500, "split_before"] = True
    whole = flight_quantities(flight.assign(split_before=False))
    split = flight_quantities(flight)

    assert split[0] == pytest.approx(whole[0] - 1.0)  # one step of duration dropped
    assert split[1] == pytest.approx(whole[1] - 0.012, rel=1e-3)  # ...and its 12 m


def test_a_flight_with_no_altitude_at_all_is_not_condemned_for_it():
    flight = _xc_flight()
    flight["alt"] = np.nan
    verdict = filter_flight(flight, FLIGHT)
    assert np.isnan(verdict.alt_range_m)
    assert verdict.drop_reason is None


def test_a_record_that_could_not_have_been_flown_is_dropped():
    # The residue fix-level cleaning cannot repair: a track riddled with null-island
    # (0, 0) positions keeps a few thousand-kilometre jumps, and each one is counted as
    # flown path. Asking the whole-flight *average* to stay under the bound that already
    # marks a single step impossible is the weakest statement that catches it.
    from soaring.analysis.preproc.flightfilter import DROP_IMPLAUSIBLE

    flight = _xc_flight()
    flight.loc[1500, "lon"] = (
        LON0 + 500_000.0 / _M_PER_DEG_LON
    )  # a 500 km jump and back
    verdict = filter_flight(flight, FLIGHT, max_mean_speed_mps=45.0)

    assert verdict.drop_reason == DROP_IMPLAUSIBLE
    assert verdict.path_km > 900.0
    # Without the bound the flight passes, which is the point of adding it.
    assert filter_flight(flight, FLIGHT).drop_reason is None


def test_the_plausibility_bound_never_touches_an_ordinary_flight():
    verdict = filter_flight(_xc_flight(), FLIGHT, max_mean_speed_mps=45.0)
    assert verdict.drop_reason is None


def test_a_flight_out_of_reach_of_its_own_origin_is_dropped():
    # The defect no per-step rule can see: the *first* fix is the corrupt one, so every
    # step is plausible and the flight simply sits 500 km from where it says it began.
    # Five archive flights failed this way, and because that fix becomes the origin of
    # the local frame, all five carried every later coordinate 4500 km off -- enough to
    # move the ensemble MSD by seven orders of magnitude.
    from soaring.analysis.preproc.flightfilter import DROP_UNREACHABLE

    flight = _xc_flight()
    flight.loc[0, ["lat", "lon"]] = [0.0, 0.0]
    flight.loc[1, "split_before"] = True  # the jump off it is not counted as flown
    verdict = filter_flight(flight, FLIGHT, max_mean_speed_mps=45.0)

    assert verdict.drop_reason == DROP_UNREACHABLE
    assert verdict.extent_km > 5000.0
    # Stated per fix, so it also catches what the extent-against-duration form could
    # not: one fix far out early in a long flight, where the whole duration would have
    # licensed the distance.
    near = _xc_flight()
    near.loc[5, "lat"] = LAT0 + 2_000.0 / _M_PER_DEG_LAT  # 2 km, five seconds in
    verdict = filter_flight(near, FLIGHT, max_mean_speed_mps=45.0)
    assert verdict.drop_reason == DROP_UNREACHABLE
    # The weaker form would have passed it: 2 km is well inside what the bound allows
    # over the whole flight, and the 4 km of path it adds is nothing against the total.
    assert 1000.0 * verdict.extent_km < 45.0 * verdict.duration_s
    assert 1000.0 * verdict.path_km / verdict.duration_s < 45.0
    # The mean-speed bound does not see it: no step of the flight is impossible.
    assert 1000.0 * verdict.path_km / verdict.duration_s < 45.0


def test_the_reach_bound_never_touches_an_ordinary_flight():
    verdict = filter_flight(_xc_flight(), FLIGHT, max_mean_speed_mps=45.0)
    assert verdict.drop_reason is None
    assert verdict.extent_km <= 45.0 * verdict.duration_s / 1000.0


def test_the_flatness_test_does_not_get_harder_as_the_stint_gets_longer():
    """A full range is a maximum statistic, and that made the rule unfireable.

    Over zero-mean noise the range grows like ``2 sigma sqrt(2 ln n)``: at the metre-
    scale barometric noise of this archive it reads about 4.6 m over 60 samples and
    7.1 m over 3000. Against a 5 m tolerance the same stationary pilot therefore
    passed on a one-minute stint and failed on a ten-minute one -- and since an
    interior ground stint has to last minutes to be considered at all, the guard could
    not fire on any of them. The statistic is the central span for that reason, and
    what is asserted here is that the verdict does not depend on how long the pilot
    stood still.
    """
    from soaring.analysis.preproc.trimming import _is_flat

    rng = np.random.default_rng(3)
    for n in (60, 300, 1200, 3000):
        t = np.arange(n, dtype=float)
        # A pilot standing still: metre-scale noise on a slowly drifting barometer.
        alt = 500.0 + 0.002 * t + rng.normal(0.0, 1.0, n)
        assert _is_flat(t, alt, tolerance_m=5.0, max_drift_mps=0.083), (
            f"{n} samples of a stationary pilot read as not flat"
        )

    # And a genuine climb is still rejected, at every length, on the rate.
    for n in (60, 300, 1200, 3000):
        t = np.arange(n, dtype=float)
        climbing = 500.0 + 1.0 * t + rng.normal(0.0, 1.0, n)
        assert not _is_flat(t, climbing, tolerance_m=5.0, max_drift_mps=0.083)


def test_a_long_gap_is_not_counted_as_flown():
    """The half of the block rule that was missing: a hole nobody marked.

    A `split_before` marker records what a *stage* decided -- an excised run, an offset,
    a mid-flight landing. A long hole in the log is nobody's decision, so no marker
    describes it, and it reached the flight-level cuts unannounced while being exactly
    the case the rule is about: ten minutes of missing record counted as ten minutes of
    flight, and the straight line across it as six kilometres flown.
    """
    from soaring.analysis.config import load_preproc_config

    sampling = load_preproc_config().sampling
    t = np.concatenate([np.arange(0.0, 600.0), np.arange(1200.0, 1800.0)])
    flight = pd.DataFrame(
        {
            "t": t,
            "lat": LAT0,
            "lon": LON0 + 10.0 * t / _M_PER_DEG_LON,
            "alt": 1000.0,
            "split_before": False,
        }
    )

    blind = flight_quantities(flight)
    aware = flight_quantities(flight, sampling)
    assert blind[0] == pytest.approx(1799.0)  # the 600 s hole counted as airborne
    assert aware[0] == pytest.approx(1198.0)  # ...and now it is not
    assert blind[1] - aware[1] == pytest.approx(6.0, abs=0.05)  # 6 km never flown


def test_the_two_duration_bounds_read_different_quantities():
    """The floor is airborne time; the ceiling is how long the recorder ran.

    They were the same number until the sum learned to skip long gaps, and then the
    ceiling silently stopped working: a logger left running overnight is *mostly*
    gap, so a bound read on the gap-excluding sum no longer catches the very case it
    was calibrated on -- the census's 16-to-166 hour "flights" with paths up to 10^4
    km, which would land in the long-lag MSD.
    """
    from soaring.analysis.preproc.flightfilter import DROP_TOO_LONG
    from soaring.analysis.config import load_preproc_config

    sampling = load_preproc_config().sampling
    # One hour of flight, twenty hours of nothing, one more hour of flight.
    t = np.concatenate([np.arange(0.0, 3600.0), np.arange(72000.0, 75600.0)])
    flight = pd.DataFrame(
        {
            "t": t,
            "lat": LAT0 + 3.0 * t / _M_PER_DEG_LAT,
            "lon": LON0 + 10.0 * t / _M_PER_DEG_LON,
            "alt": 2000.0 - 0.05 * t,
            "split_before": False,
        }
    )
    verdict = filter_flight(flight, FLIGHT, max_mean_speed_mps=45.0, sampling=sampling)
    assert verdict.drop_reason == DROP_TOO_LONG
    # And it is the span that catches it: the airborne sum is two ordinary hours.
    assert verdict.duration_s == pytest.approx(7198.0)
    assert verdict.duration_s < FLIGHT.max_duration_s
