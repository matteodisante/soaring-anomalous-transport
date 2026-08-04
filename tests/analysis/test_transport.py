import numpy as np
import pandas as pd
import pytest

from soaring.analysis.transport import (
    MSDAccumulator,
    ensemble_msd,
    fit_msd_exponent,
    log_lag_grid,
)


def _flight(flight_id, t, east, north):
    return pd.DataFrame({"flight_id": flight_id, "t": t, "E": east, "N": north})


def _ballistic(flight_id, speed, heading, duration=1000.0, dt=1.0):
    """A straight flight at constant speed: MSD = v^2 t^2 exactly, so alpha = 2."""
    t = np.arange(0.0, duration + dt, dt)
    return _flight(
        flight_id, t, speed * t * np.cos(heading), speed * t * np.sin(heading)
    )


def _random_walk(flight_id, rng, step_m=10.0, duration=2000.0, dt=1.0):
    """An uncorrelated walk: MSD = 2 D t, so alpha = 1."""
    t = np.arange(0.0, duration + dt, dt)
    angle = rng.uniform(0.0, 2.0 * np.pi, t.size - 1)
    east = np.concatenate([[0.0], np.cumsum(step_m * np.cos(angle))])
    north = np.concatenate([[0.0], np.cumsum(step_m * np.sin(angle))])
    return _flight(flight_id, t, east, north)


def test_a_ballistic_ensemble_gives_exactly_two():
    # Every flight travels at 12 m/s in its own direction: |r(t)| = 12 t whatever the
    # heading, so the MSD is 144 t^2 and the exponent is exact.
    # Integer lags, so each lands exactly on a sampled time and the curve is the
    # analytic one rather than its nearest-fix staircase.
    lags = np.unique(np.round(log_lag_grid(900.0, 10.0, 40)))
    fixes = pd.concat(
        [_ballistic(i, 12.0, 2.0 * np.pi * i / 20.0) for i in range(20)],
        ignore_index=True,
    )
    result = ensemble_msd(fixes, lags)

    assert result.msd == pytest.approx(144.0 * lags**2, rel=1e-6)
    assert (result.n_flights == 20).all()
    fit = fit_msd_exponent(result, t_min_s=10.0, t_max_s=900.0, min_flights=10)
    assert fit.alpha == pytest.approx(2.0, abs=1e-6)
    assert fit.prefactor == pytest.approx(144.0, rel=1e-3)


def test_a_random_walk_ensemble_gives_one():
    rng = np.random.default_rng(20260803)
    lags = log_lag_grid(1000.0, 10.0, 40)
    fixes = pd.concat([_random_walk(i, rng) for i in range(400)], ignore_index=True)
    result = ensemble_msd(fixes, lags)

    fit = fit_msd_exponent(result, t_min_s=10.0, t_max_s=1000.0, min_flights=100)
    assert fit.alpha == pytest.approx(1.0, abs=0.05)
    # MSD = n_steps * step^2 = t * 100 m^2/s for a 1 s cadence and 10 m steps.
    assert fit.prefactor == pytest.approx(100.0, rel=0.15)


def test_the_ensemble_thins_out_with_the_lag():
    # Only flights that lasted at least t contribute to MSD(t), and the count is
    # reported so that a fit range can be chosen against it rather than in ignorance.
    lags = np.array([100.0, 500.0, 900.0, 1500.0])
    short = _ballistic(0, 10.0, 0.0, duration=600.0)
    long = _ballistic(1, 10.0, 0.0, duration=2000.0)
    result = ensemble_msd(pd.concat([short, long], ignore_index=True), lags)

    assert result.n_flights.tolist() == [2, 2, 1, 1]
    assert result.msd[0] == pytest.approx(1e6)  # both flights at 1000 m
    assert result.msd[2] == pytest.approx(81e6)  # only the long one, at 9000 m


def test_a_lag_no_flight_covers_is_nan_not_zero():
    lags = np.array([100.0, 5000.0])
    result = ensemble_msd(_ballistic(0, 10.0, 0.0, duration=600.0), lags)
    assert np.isfinite(result.msd[0])
    assert np.isnan(result.msd[1])
    assert result.n_flights.tolist() == [1, 0]


def test_a_gap_in_a_flight_costs_only_the_lags_inside_it():
    # A segment keeps the parent clock, so a split flight contributes at every elapsed
    # time some segment covers -- and nothing at the times that fall in the gap.
    flight = _ballistic(0, 10.0, 0.0, duration=1000.0)
    flight = flight[(flight["t"] < 300.0) | (flight["t"] > 600.0)]
    lags = np.array([200.0, 450.0, 800.0])
    result = ensemble_msd(flight, lags)

    assert result.n_flights.tolist() == [1, 0, 1]
    assert result.msd[0] == pytest.approx(4e6)
    assert result.msd[2] == pytest.approx(64e6)


def test_the_coverage_tolerance_follows_the_flights_own_cadence():
    # Half a step of the flight's *own* cadence: a 10 s logger answers for a lag 4 s
    # past its last fix and not for one 6 s past, while a 1 Hz logger stops half a
    # second past. A fixed tolerance would either mute the slow loggers or let a fast
    # one answer for a time it never sampled.
    slow = _ballistic(0, 10.0, 0.0, duration=1000.0, dt=10.0)
    assert ensemble_msd(slow, np.array([1004.0, 1006.0])).n_flights.tolist() == [1, 0]
    fast = _ballistic(0, 10.0, 0.0, duration=1000.0, dt=1.0)
    assert ensemble_msd(fast, np.array([1000.4, 1001.0])).n_flights.tolist() == [1, 0]


def test_the_accumulator_streams_flight_by_flight():
    # The archive does not fit in memory, so the curve has to be built by streaming;
    # accumulating in two batches must give exactly what one pass gives.
    lags = log_lag_grid(900.0, 10.0, 20)
    flights = [_ballistic(i, 10.0 + i, 0.3 * i) for i in range(6)]
    whole = ensemble_msd(pd.concat(flights, ignore_index=True), lags)

    accumulator = MSDAccumulator(lags)
    for flight in flights:
        accumulator.add(
            flight["t"].to_numpy(), flight["E"].to_numpy(), flight["N"].to_numpy()
        )
    streamed = accumulator.result()

    assert streamed.msd == pytest.approx(whole.msd)
    assert streamed.n_flights.tolist() == whole.n_flights.tolist()


def test_the_fit_refuses_a_range_with_too_few_flights():
    lags = log_lag_grid(900.0, 10.0, 20)
    result = ensemble_msd(_ballistic(0, 10.0, 0.0), lags)
    with pytest.raises(ValueError, match="nothing to fit"):
        fit_msd_exponent(result, t_min_s=10.0, t_max_s=900.0, min_flights=100)


def test_a_flight_says_nothing_about_lags_below_its_own_cadence():
    # A 10 s logger has no fix at t = 1 s. The half-step tolerance alone would let it
    # answer with its fix at t = 0 -- a displacement of exactly zero -- and a
    # slow-cadence minority would then drag the short-lag MSD towards zero until the lag
    # grid crossed their step.
    slow = _ballistic(0, 10.0, 0.0, duration=1000.0, dt=10.0)
    result = ensemble_msd(slow, np.array([1.0, 4.0, 10.0, 20.0]))
    assert result.n_flights.tolist() == [0, 0, 1, 1]
    assert result.msd[2] == pytest.approx(1e4)  # 100 m at t = 10 s


def test_the_time_averaged_msd_of_a_straight_flight_is_exact():
    # Ballistic: |r(t0+tau) - r(t0)| = v tau for every starting point, so the time
    # average is v^2 tau^2 whatever the window -- an answer to machine precision.
    from soaring.analysis.transport import time_averaged_msd

    t = np.arange(0.0, 600.0)
    delta2 = time_averaged_msd(9.0 * t, 12.0 * t, 1.0)  # |v| = 15 m/s
    lags = np.arange(delta2.size, dtype=float)
    assert delta2[0] == pytest.approx(0.0, abs=1e-6)
    assert delta2[1:400] == pytest.approx(225.0 * lags[1:400] ** 2, rel=1e-9)


def test_the_time_averaged_msd_matches_the_direct_double_loop():
    # The FFT identity is worth one test against the O(n^2) definition it replaces.
    from soaring.analysis.transport import time_averaged_msd

    rng = np.random.default_rng(11)
    east = np.cumsum(rng.normal(0.0, 3.0, 200))
    north = np.cumsum(rng.normal(0.0, 3.0, 200))
    fast = time_averaged_msd(east, north, 1.0)
    slow = np.array(
        [
            np.mean(
                (east[k:] - east[: len(east) - k]) ** 2
                + (north[k:] - north[: len(north) - k]) ** 2
            )
            if k
            else 0.0
            for k in range(len(east))
        ]
    )
    assert fast[:150] == pytest.approx(slow[:150], rel=1e-8, abs=1e-8)


def test_a_segment_too_short_gives_nan():
    from soaring.analysis.transport import time_averaged_msd

    assert np.isnan(time_averaged_msd(np.array([1.0]), np.array([2.0]), 1.0)).all()


def test_the_time_averaged_accumulator_pools_cadences_on_one_lag_axis():
    # Segments of different cadence contribute at the lags each can resolve, on a shared
    # *time* axis: a 5 s logger answers at 5 s and not at 1 s, and both answer at 10 s.
    from soaring.analysis.transport import TAMSDAccumulator

    lags = np.array([1.0, 5.0, 10.0, 100.0])
    accumulator = TAMSDAccumulator(lags)
    t_fast = np.arange(0.0, 200.0, 1.0)
    accumulator.add(10.0 * t_fast, np.zeros_like(t_fast), 1.0)
    t_slow = np.arange(0.0, 200.0, 5.0)
    accumulator.add(10.0 * t_slow, np.zeros_like(t_slow), 5.0)
    result = accumulator.result()

    # Half of 200 samples at 1 s and half of 40 at 5 s both reach 100 s, so the last
    # lag is answered by both -- on the same time axis, from different cadences.
    assert result.n_flights.tolist() == [1, 2, 2, 2]
    assert result.msd[0] == pytest.approx(100.0)  # 10 m/s over 1 s, the fast one alone
    assert result.msd[2] == pytest.approx(1e4)  # 100 m over 10 s, both agree
    assert result.msd[3] == pytest.approx(1e6)  # 1 km over 100 s


def test_the_time_averaged_accumulator_cuts_the_lags_a_segment_cannot_support():
    # Past half a segment's length the time average has a handful of starting points
    # left and stops being an average; those lags are not answered rather than answered
    # badly.
    from soaring.analysis.transport import TAMSDAccumulator

    lags = np.array([10.0, 40.0, 60.0, 200.0])
    accumulator = TAMSDAccumulator(lags)
    t = np.arange(0.0, 101.0)
    accumulator.add(10.0 * t, np.zeros_like(t), 1.0)
    assert accumulator.result().n_flights.tolist() == [1, 1, 0, 0]


def test_the_fit_range_stops_where_the_ensemble_thins_out():
    # The upper end is not a choice but a consequence: past it the average is over the
    # flights that kept going rather than over the population.
    from soaring.analysis.transport import coverage_limited_range

    lags = np.array([100.0, 200.0, 400.0, 800.0, 1600.0])
    short = [_ballistic(i, 10.0, 0.0, duration=500.0) for i in range(8)]
    long = [_ballistic(100 + i, 10.0, 0.0, duration=2000.0) for i in range(2)]
    result = ensemble_msd(pd.concat(short + long, ignore_index=True), lags)

    assert result.n_flights.tolist() == [10, 10, 10, 2, 2]
    # 2 of 10 is under a quarter, so the range stops before 800 s.
    assert coverage_limited_range(result, t_min_s=100.0) == (100.0, 400.0)
    # A looser demand keeps more of the curve.
    assert coverage_limited_range(result, t_min_s=100.0, min_coverage=0.1)[1] == 1600.0


def test_the_percentiles_describe_the_same_flights_as_the_mean():
    # The bands are the reason the first archive-wide MSD was caught as wrong: a mean
    # seven orders of magnitude above its own median is not a curve, it is an outlier.
    # For that reading to be sound the two must be computed over the same population.
    lags = np.array([1.0, 2.0, 4.0])
    acc = MSDAccumulator(lags, keep_samples=True)
    # Nine flights of unit speed and one a thousand times faster.
    for speed in [1.0] * 9 + [1000.0]:
        t = np.arange(0.0, 9.0)
        acc.add(t, speed * t, np.zeros_like(t))
    result = acc.result()

    for i, lag in enumerate(lags):
        assert result.p50[i] == pytest.approx(lag**2)
        assert result.p10[i] == pytest.approx(lag**2)
        assert result.p90[i] > lag**2  # the outlier is inside the upper decile
        # The mean is dragged by the single flight; the median is not. That gap is
        # the diagnostic, so it must be a real difference and not a population artefact.
        assert result.msd[i] > 1e4 * result.p50[i]
    assert (result.n_flights == 10).all()


def test_percentiles_are_absent_rather_than_wrong_when_samples_are_not_kept():
    lags = np.array([1.0, 2.0])
    acc = MSDAccumulator(lags, keep_samples=False)
    t = np.arange(0.0, 5.0)
    acc.add(t, t, np.zeros_like(t))
    result = acc.result()
    assert result.p50 is None and result.p10 is None and result.p90 is None
    assert np.isfinite(result.msd).all()


@pytest.mark.parametrize("hurst", [0.3, 0.5, 0.7])
def test_the_fit_recovers_the_exponent_of_a_process_that_has_one(hurst):
    # Fractional Brownian motion has <|r(t)|^2> = 2 t^(2H) in the plane, exactly, so
    # it is the one ensemble whose answer is known in advance for an alpha that is
    # neither 1 nor 2. Built by Cholesky on the exact covariance, which is slow but
    # leaves no discretisation error to be confused with a fitting error.
    #
    # The tolerance is set from the sampling, not from `alpha_err`, which understates
    # the truth here: every lag is estimated from the *same* flights, so residuals are
    # strongly correlated and the ordinary-least-squares error bar does not see it. At
    # 2000 flights the recovered exponent sits within 0.02 of 2H for each H below, and
    # the deviation halves again when the ensemble is quadrupled -- 1/sqrt(N), which is
    # what an unbiased estimator of a noisy mean does.
    n, flights = 128, 2000
    t = np.arange(1, n + 1, dtype=float)
    cov = 0.5 * (
        t[:, None] ** (2 * hurst)
        + t[None, :] ** (2 * hurst)
        - np.abs(t[:, None] - t[None, :]) ** (2 * hurst)
    )
    chol = np.linalg.cholesky(cov + 1e-9 * np.eye(n))
    rng = np.random.default_rng(4)

    lags = np.arange(1.0, 33.0)
    acc = MSDAccumulator(lags, keep_samples=False)
    full_t = np.arange(0.0, n + 1)
    for _ in range(flights):
        walk = chol @ rng.normal(size=(n, 2))
        acc.add(full_t, np.r_[0.0, walk[:, 0]], np.r_[0.0, walk[:, 1]])
    result = acc.result()

    fit = fit_msd_exponent(result, t_min_s=1.0, t_max_s=32.0, min_flights=100)
    assert fit.alpha == pytest.approx(2 * hurst, abs=0.04)


def test_a_fixed_duration_cohort_separates_selection_from_motion():
    # The one methodological weakness of an ensemble MSD over records of unequal length:
    # only flights lasting at least t contribute to MSD(t), so the population behind the
    # curve changes as the lag grows. If the flights that last longer are also the ones
    # that move faster -- and in an archive of cross-country flights they are -- the
    # curve steepens for a reason that has nothing to do with the motion.
    #
    # Here every flight is exactly diffusive, alpha = 1, and the only thing correlated
    # with duration is speed. The pooled exponent must be visibly wrong, and a cohort --
    # flights all long enough to be present at every lag of the range -- must recover 1.
    rng = np.random.default_rng(19)
    lags = log_lag_grid(4000.0, 10.0, 40)
    pooled = MSDAccumulator(lags, keep_samples=False)
    cohort = MSDAccumulator(lags, keep_samples=False)

    for _ in range(600):
        duration = float(rng.choice([1000, 2000, 4000, 8000]))
        speed = 1.0 + 3.0 * duration / 8000.0  # long flights are the fast ones
        t = np.arange(0.0, duration + 1.0)
        step = speed * rng.normal(0.0, 4.0, (t.size, 2))
        step[0] = 0.0
        walk = np.cumsum(step, axis=0)
        pooled.add(t, walk[:, 0], walk[:, 1])
        if duration >= 4000.0:
            cohort.add(t, walk[:, 0], walk[:, 1])

    window = {"t_min_s": 100.0, "t_max_s": 4000.0, "min_flights": 30}
    pooled_fit = fit_msd_exponent(pooled.result(), **window)
    cohort_fit = fit_msd_exponent(cohort.result(), **window)

    assert pooled_fit.alpha > 1.05, (
        "the artefact this control exists for did not appear"
    )
    assert cohort_fit.alpha == pytest.approx(1.0, abs=0.05)
    assert abs(cohort_fit.alpha - 1.0) < abs(pooled_fit.alpha - 1.0)


def test_a_segment_says_nothing_about_lags_below_its_own_step():
    # The time-averaged twin of `test_a_flight_says_nothing_about_lags_below_its_own
    # _cadence`. Without it a 10 s segment answered a lag of 6 s with its value at 10 s
    # -- 2.8 times too large -- so every slow-cadence segment inflated the short-lag end
    # of the curve, and the two estimators were no longer measuring the same thing.
    from soaring.analysis.transport import TAMSDAccumulator

    lags = np.array([5.0, 6.0, 9.0, 10.0, 20.0])
    accumulator = TAMSDAccumulator(lags)
    t = np.arange(200) * 10.0
    accumulator.add(2.0 * t, np.zeros(t.size), 10.0)  # ballistic, 2 m/s
    result = accumulator.result()

    assert result.n_flights.tolist() == [0, 0, 0, 1, 1]
    assert result.msd[3] == pytest.approx(400.0)  # (2 * 10)^2
    assert result.msd[4] == pytest.approx(1600.0)  # (2 * 20)^2


def test_the_bootstrap_error_on_alpha_is_the_honest_one():
    """The reported uncertainty must be the sampling one, not the least-squares one.

    `fit_msd_exponent` returns the OLS error on the slope, which treats the residual at
    each lag as an independent draw. Every lag is an average over the *same* flights, so
    they are nothing of the kind: one flight that happens to fly far tilts the whole
    curve instead of scattering one point. Measured against the truth -- the scatter of
    alpha over independent ensembles of the same process -- the OLS error understates by
    about five times and the flight-resampling bootstrap lands on it.
    """
    from soaring.analysis.transport import bootstrap_alpha_error

    rng = np.random.default_rng(4)
    hurst, n = 0.7, 128
    t = np.arange(1, n + 1, dtype=float)
    cov = 0.5 * (
        t[:, None] ** (2 * hurst)
        + t[None, :] ** (2 * hurst)
        - np.abs(t[:, None] - t[None, :]) ** (2 * hurst)
    )
    chol = np.linalg.cholesky(cov + 1e-9 * np.eye(n))
    lags = np.arange(1.0, 33.0)
    full_t = np.arange(0.0, n + 1)

    alphas, ols, boot = [], [], []
    for _ in range(12):
        accumulator = MSDAccumulator(lags, keep_samples=True)
        for _ in range(300):
            walk = chol @ rng.normal(size=(n, 2))
            accumulator.add(full_t, np.r_[0.0, walk[:, 0]], np.r_[0.0, walk[:, 1]])
        fit = fit_msd_exponent(
            accumulator.result(), t_min_s=1.0, t_max_s=32.0, min_flights=100
        )
        alphas.append(fit.alpha)
        ols.append(fit.alpha_err)
        boot.append(
            bootstrap_alpha_error(
                accumulator.stacked_samples(),
                lags,
                t_min_s=1.0,
                t_max_s=32.0,
                n_resamples=80,
            )
        )

    truth = float(np.std(alphas, ddof=1))
    assert truth / np.mean(ols) > 3.0, "the OLS error is supposed to be the wrong one"
    assert 0.5 < truth / np.mean(boot) < 2.0, (
        f"the bootstrap should land near the truth: {truth:.4f} against "
        f"{np.mean(boot):.4f}"
    )


def test_the_local_slope_is_robust_to_a_single_bad_lag():
    """The estimator behind panel (c) has to survive one lag knocked out.

    The short-lag end of a real ensemble MSD carries coverage artefacts of a few per
    cent -- a coarse logger answering a lag it does not sample with a neighbouring
    fix -- and a least-squares window tilts under one of them where a median of
    pairwise slopes does not. The panel is read as evidence about the exponent, so
    its estimator must not turn one bad point into a bend.
    """
    from soaring.analysis.transport import MSDResult, local_slope

    lags = np.geomspace(1.0, 1000.0, 60)
    clean = MSDResult(
        t=lags,
        msd=3.0 * lags**1.6,
        n_flights=np.full(lags.size, 1000),
        sem=np.zeros(lags.size),
    )
    slope, error = local_slope(clean)
    inside = np.isfinite(slope)
    assert slope[inside] == pytest.approx(1.6, abs=1e-6)
    assert np.nanmax(error[inside]) < 1e-6, "a perfect power law has no slope scatter"

    # One lag displaced by 5 %, which is the scale the archive shows at short lag.
    spoiled = clean.msd.copy()
    spoiled[30] *= 1.05
    hurt = MSDResult(t=lags, msd=spoiled, n_flights=clean.n_flights, sem=clean.sem)
    robust, robust_err = local_slope(hurt)
    near = np.abs(np.log10(lags) - np.log10(lags[30])) <= 0.15
    assert np.nanmax(np.abs(robust[near] - 1.6)) < 0.05, (
        "one displaced lag should barely move a median of pairwise slopes"
    )
    # And the error bar grows where the window is disturbed, which is the point of it.
    assert np.nanmax(robust_err[near]) > 10 * np.nanmax(error[inside])
