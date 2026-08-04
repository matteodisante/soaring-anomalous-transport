"""Regime detection has to be able to say "one regime", or it is not a measurement."""

from __future__ import annotations

import numpy as np
import pytest

from soaring.analysis.observables import regimes as R

RNG = np.random.default_rng(4)
X = np.geomspace(1.0, 1e4, 60)


def _noisy(y, scale=0.01, seed=0):
    return y * (1.0 + scale * np.random.default_rng(seed).normal(size=len(y)))


def test_a_pure_power_law_gets_no_breakpoint():
    chosen = R.select_breakpoints(X, _noisy(3.0 * X**1.5, seed=1))
    assert chosen["n_breaks"] == 0
    assert chosen["slopes"][0] == pytest.approx(1.5, abs=0.05)


def test_a_sharp_two_regime_curve_is_found():
    y = np.where(X < 300, X**1.0, 300.0 ** (1.0 - 2.0) * X**2.0)
    chosen = R.select_breakpoints(X, _noisy(y, seed=2))
    assert chosen["n_breaks"] >= 1
    assert min(chosen["breaks_s"]) < 600
    assert chosen["slopes"][0] == pytest.approx(1.0, abs=0.2)
    assert chosen["slopes"][-1] == pytest.approx(2.0, abs=0.2)


def test_effective_dof_is_far_below_the_point_count_for_a_smooth_curve():
    """Correlated residuals are the reason an exponent cannot be quoted to four places."""
    smooth = 3.0 * X**1.5 * (1.0 + 0.05 * np.sin(np.log(X)))
    assert R.effective_dof(X, smooth) < 0.25 * len(X)
    scattered = _noisy(3.0 * X**1.5, scale=0.05, seed=3)
    assert R.effective_dof(X, scattered) > R.effective_dof(X, smooth)


def test_the_default_null_is_flagged_as_circular():
    """Reading the noise off the residuals tests a curve against its own structure."""
    bent = 3.0 * X**1.5 * (1.0 + 0.3 * np.tanh(np.log10(X) - 2))
    circular = R.spurious_breakpoints(X, bent, n_surrogates=40, seed=0)
    assert circular["circular"] is True
    honest = R.spurious_breakpoints(
        X, bent, n_surrogates=40, seed=0, sigma=0.01, autocorrelation=0.3
    )
    assert honest["circular"] is False
    assert honest["false_positive_rate"] < circular["false_positive_rate"]


def test_smooth_crossover_measures_the_width_of_a_bend():
    sharp = np.where(X < 300, X**1.0, 300.0 ** (1.0 - 2.0) * X**2.0)
    fitted = R.smooth_crossover(X, sharp)
    assert fitted is not None
    assert fitted["alpha_low"] == pytest.approx(1.0, abs=0.25)
    assert fitted["alpha_high"] == pytest.approx(2.0, abs=0.25)
    assert fitted["tau_s"] == pytest.approx(300.0, rel=0.6)


def test_piecewise_fit_is_continuous_at_its_knots():
    x = np.linspace(0.0, 4.0, 60)
    y = np.where(x < 2.0, x, 2.0 + 3.0 * (x - 2.0))
    _, rss, predict = R.piecewise_fit(x, y, np.array([2.0]))
    assert rss < 1e-18
    assert predict(np.array([2.0]))[0] == pytest.approx(2.0, abs=1e-9)
