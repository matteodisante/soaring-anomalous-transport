"""The velocity autocorrelation and its Green--Kubo tail exponent, tested against known cases."""

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
