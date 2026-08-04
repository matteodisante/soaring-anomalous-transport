"""The inspection bias is worth an error of a whole unit, so it gets a test that measures it."""

from __future__ import annotations

import numpy as np
import pytest

from soaring.analysis.observables import persistence as P
from soaring.analysis.observables import synthetic as S


def test_velocity_autocorrelation_decays_over_the_persistence_time():
    track = S.persistent_walk(40000, 200.0, seed=1)
    velocity = np.diff(track, axis=0)
    lags, correlation = P.velocity_autocorrelation(velocity, max_lag=800)
    assert correlation[0] == pytest.approx(1.0)
    # exp(-t/tau) crosses 1/e at tau.
    crossing = int(np.argmax(correlation < np.exp(-1.0)))
    assert 100 < crossing < 400


def test_an_uncorrelated_walk_decorrelates_immediately():
    velocity = np.diff(S.brownian(20000, seed=2), axis=0)
    _, correlation = P.velocity_autocorrelation(velocity, max_lag=50)
    assert abs(correlation[1]) < 0.1


def test_runs_do_not_overlap_and_tile_the_record():
    track = S.persistent_walk(5000, 100.0, seed=3)
    lengths = P.persistence_runs(track, 1.15)
    assert lengths.sum() <= len(track)
    assert lengths.sum() > 0.8 * len(track)


def test_per_instant_sampling_recovers_a_tail_index_one_lower():
    """The reason persistence_runs exists, measured rather than asserted.

    A Pareto run-length distribution sampled at every instant is length-biased, so its
    tail index comes out one below the truth. At the values expected here that is not a
    bias to correct afterwards; it is a different answer.
    """
    rng = np.random.default_rng(7)
    beta = 2.0
    lengths = np.ceil(20.0 * (1.0 + rng.pareto(beta, 4000))).astype(int)

    unbiased, _ = P.tail_index(lengths)
    # Length-biased: each run appears in proportion to its length.
    weights = lengths / lengths.sum()
    drawn = rng.choice(lengths, size=8000, p=weights)
    biased, _ = P.tail_index(drawn)

    assert unbiased == pytest.approx(beta, abs=0.3)
    assert biased == pytest.approx(beta - 1.0, abs=0.35)
    assert unbiased - biased > 0.5


def test_tail_index_recovers_a_known_pareto():
    rng = np.random.default_rng(11)
    for beta in (1.5, 2.5):
        sample = 10.0 * (1.0 + rng.pareto(beta, 6000))
        estimate, cut = P.tail_index(sample)
        assert estimate == pytest.approx(beta, rel=0.2)
        assert cut > 0


def test_a_straight_record_is_one_run():
    line = np.column_stack([np.arange(2000.0), np.zeros(2000)])
    assert P.persistence_runs(line, 1.05).size == 1


def test_the_two_samplers_disagree_on_the_same_record():
    track = S.persistent_walk(20000, 150.0, seed=5)
    honest = P.persistence_runs(track, 1.15)
    biased = P.inspection_biased_runs(track, 1.15, stride=7)
    assert biased.mean() > honest.mean()


def test_the_vectorised_scan_is_the_scalar_one():
    """The optimisation must be an optimisation, not a change of definition.

    Walking the endpoint sample by sample and finding the first violation with an argmax
    are the same rule; the second is seven times faster, which is three hours against
    twenty-six minutes over the archive. Equality is asserted rather than assumed, across
    three processes and three thresholds, because a scan that silently drifted would move
    every run-length statistic in the chapter.
    """
    def scalar(positions, max_sinuosity):
        n = len(positions)
        if n < 2:
            return np.empty(0, dtype=int)
        step = np.hypot(*np.diff(positions, axis=0).T)
        arc = np.concatenate([[0.0], np.cumsum(step)])
        out, start = [], 0
        while start < n - 1:
            end = start + 1
            while end < n:
                chord = float(np.hypot(*(positions[end] - positions[start])))
                if chord <= 0 or (arc[end] - arc[start]) / chord > max_sinuosity:
                    break
                end += 1
            out.append(end - start)
            start = end
        return np.asarray(out, dtype=int)

    for seed in range(4):
        for track in (
            S.persistent_walk(3000, 80.0, seed=seed),
            S.brownian(3000, seed=seed),
            S.levy_walk(3000, 1.6, seed=seed),
        ):
            for threshold in (1.05, 1.15, 1.30):
                np.testing.assert_array_equal(
                    P.persistence_runs(track, threshold), scalar(track, threshold)
                )


def test_vacf_tail_exponent_recovers_a_known_power_law():
    """A correlation built as tau^-0.4 must read gamma = 0.4 and imply alpha = 1.6."""
    from soaring.analysis.observables.persistence import vacf_tail_exponent

    lags = np.geomspace(10.0, 2000.0, 30)
    gamma, alpha, n = vacf_tail_exponent(lags, lags**-0.4)
    assert gamma == pytest.approx(0.4, abs=1e-8)
    assert alpha == pytest.approx(1.6, abs=1e-8)
    assert n == 30


def test_vacf_tail_exponent_drops_the_lags_where_the_correlation_has_gone_negative():
    """Lags where C <= 0 carry no power law; the fit uses the positive ones and says so."""
    from soaring.analysis.observables.persistence import vacf_tail_exponent

    lags = np.geomspace(10.0, 2000.0, 30)
    correlation = lags**-0.4
    correlation[6:] = -0.1
    gamma, _, n = vacf_tail_exponent(lags, correlation)
    assert n == 6
    assert gamma == pytest.approx(0.4, abs=1e-8)

    correlation[3:] = -0.1
    gamma, alpha, n = vacf_tail_exponent(lags, correlation)
    assert n == 0
    assert np.isnan(gamma) and np.isnan(alpha)


def test_vacf_tail_exponent_honours_the_fit_range():
    """Outside the stated range the curve is a different power law; only the range is fitted."""
    from soaring.analysis.observables.persistence import vacf_tail_exponent

    lags = np.geomspace(1.0, 1000.0, 60)
    correlation = np.where(lags < 50, lags**-1.5, 50.0**-1.5 * (lags / 50) ** -0.3)
    gamma, _, n = vacf_tail_exponent(lags, correlation, fit_range=(50.0, 1000.0))
    assert gamma == pytest.approx(0.3, abs=1e-6)
    assert n < lags.size


def test_vacf_tail_exponent_is_the_one_sided_bound_the_docstring_claims():
    """Removing the record mean steepens the tail, so the measured gamma is an upper bound."""
    from soaring.analysis.observables.persistence import (
        vacf_tail_exponent,
        velocity_autocorrelation,
    )

    rng = np.random.default_rng(11)
    n = 20000
    # An Ornstein-Uhlenbeck velocity: C(tau) = exp(-tau/theta), plus a constant course.
    theta = 400.0
    noise = rng.standard_normal((n, 2))
    velocity = np.zeros((n, 2))
    decay = np.exp(-1.0 / theta)
    for i in range(1, n):
        velocity[i] = decay * velocity[i - 1] + np.sqrt(1 - decay**2) * noise[i]
    lags, measured = velocity_autocorrelation(velocity + np.array([8.0, 0.0]), max_lag=2000)
    truth = np.exp(-lags / theta)
    window = (lags >= 100) & (lags <= 1500)
    gamma_measured, _, _ = vacf_tail_exponent(lags[window], measured[window])
    gamma_truth, _, _ = vacf_tail_exponent(lags[window], truth[window])
    assert gamma_measured > gamma_truth


@pytest.mark.parametrize("threshold", [1.05, 1.15, 1.30])
def test_every_emitted_run_respects_the_threshold_that_defines_it(threshold):
    """The property the estimator claims, tested on the runs it actually emits.

    The scan used to look for a violation only from start + min_length, so a stretch that
    broke the threshold immediately was emitted at exactly that floor, unchecked. On
    Brownian positions at 1.05 that was 99.8 per cent of the runs, and 99.1 per cent of them
    violated the threshold; the reported median was the floor rather than a measurement.
    Neither of the two tests here caught it: the equivalence test compared against a scalar
    reference carrying the identical floor, and the tiling test is satisfied perfectly by
    floor-length runs. This one asks the estimator for its own contract.
    """
    for seed in range(3):
        track = np.asarray(S.brownian(4000, seed=seed))
        step = np.hypot(*np.diff(track, axis=0).T)
        arc = np.concatenate([[0.0], np.cumsum(step)])
        lengths = P.persistence_runs(track, threshold)
        edges = np.concatenate([[0], np.cumsum(lengths)])
        for a, b in zip(edges[:-1], edges[1:]):
            if b - a < 2:
                continue
            chord = float(np.hypot(*(track[b - 1] - track[a])))
            assert chord > 0
            assert (arc[b - 1] - arc[a]) / chord <= threshold + 1e-9
