"""Every routine must survive the inputs the archive will eventually hand it.

A pass over 155,788 flights meets an empty segment, a one-sample record, a constant
velocity and a degenerate fit, and it meets them at hour two of a four-hour run. A routine
that raises there costs the whole pass; a routine that returns a plausible number there is
worse. These pin the behaviour rather than assume it.
"""

from __future__ import annotations

import numpy as np
import pytest

from soaring.analysis.observables import moments as M
from soaring.analysis.observables import persistence as P
from soaring.analysis.observables import regimes as R
from soaring.analysis.observables import variations as V
from soaring.analysis.stats.bootstrap import cluster_bootstrap, intraclass_correlation


def test_variations_return_nan_rather_than_raising_on_impossible_lags():
    out = V.filtered_variation(np.zeros((5, 2)), np.array([1, 100]), order=2)
    assert np.isnan(out[1])


def test_variations_survive_an_empty_or_single_sample_track():
    assert np.isnan(V.filtered_variation(np.zeros((0, 2)), np.array([1]))).all()
    assert np.isnan(V.filtered_variation(np.zeros((1, 2)), np.array([1]))).all()


def test_a_fit_with_nothing_to_fit_returns_nan_not_a_number():
    hurst, residual = V.hurst_from_variations(np.array([1.0, 2, 3]), np.full(3, np.nan))
    assert np.isnan(hurst) and np.isnan(residual)


def test_net_drift_of_a_single_point_is_zero_not_a_division_by_zero():
    assert np.all(V.net_drift(np.zeros((1, 2))) == 0.0)


def test_effective_dof_never_returns_less_than_two():
    assert R.effective_dof(np.array([1.0, 2, 3, 4]), np.array([1.0, 1, 1, 1])) >= 2.0


def test_breakpoint_selection_on_a_flat_curve_finds_no_break():
    lags = np.geomspace(1.0, 100.0, 30)
    assert R.select_breakpoints(lags, np.ones(30))["n_breaks"] == 0


def test_moment_spectrum_on_a_track_shorter_than_its_lag():
    moments, tail, counts = M.moment_spectrum(np.zeros((5, 2)), np.array([1, 50]))
    assert counts[1] == 0 and np.isnan(moments[1]).all()


def test_quantile_ratios_refuse_a_quantile_the_sample_cannot_support():
    """A 99th percentile from twenty samples is not a percentile."""
    track = np.cumsum(np.random.default_rng(0).normal(size=(300, 2)), axis=0)
    ratios = M.quantile_ratios(track, np.array([100]), probabilities=(0.99,))
    assert np.isnan(ratios).all()


def test_persistence_runs_on_a_track_shorter_than_the_minimum():
    assert P.persistence_runs(np.zeros((3, 2)), 1.1).size == 0


def test_tail_index_refuses_a_sample_too_small_to_fit():
    beta, cut = P.tail_index(np.array([1.0, 2.0, 3.0]))
    assert np.isnan(beta) and cut == 0


def test_autocorrelation_of_a_constant_velocity_is_not_a_division_by_zero():
    lags, correlation = P.velocity_autocorrelation(np.ones((100, 2)))
    assert lags.size == 0 and correlation.size == 0


def test_intraclass_correlation_of_one_cluster_is_zero():
    assert intraclass_correlation(np.arange(10.0), np.zeros(10, int)) == 0.0


def test_cluster_bootstrap_with_a_single_cluster_does_not_hang_or_raise():
    point, replicates = cluster_bootstrap(
        np.ones((1, 3)), np.zeros(1, int), lambda c: c[0], n_resamples=5
    )
    assert point == pytest.approx(1.0)
    assert replicates.shape == (5,)
