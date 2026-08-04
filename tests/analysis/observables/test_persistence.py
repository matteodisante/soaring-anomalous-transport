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
