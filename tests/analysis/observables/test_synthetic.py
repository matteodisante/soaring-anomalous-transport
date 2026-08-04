"""The generators must produce the exponent they advertise, or nothing below is testable.

These come before the observables. An estimator validated against a generator that is
itself wrong is validated against nothing, and the failure is invisible: both are plausible
numbers.
"""

from __future__ import annotations

import numpy as np
import pytest

from soaring.analysis.observables import synthetic as S


def msd_exponent(positions, lo=4, hi=256):
    """A plain overlapping-increment MSD fit, deliberately independent of the package."""
    lags = np.unique(np.round(np.geomspace(lo, hi, 20)).astype(int))
    msd = [((positions[k:] - positions[:-k]) ** 2).sum(1).mean() for k in lags]
    return float(np.polyfit(np.log(lags), np.log(msd), 1)[0])


def test_brownian_is_diffusive():
    alphas = [msd_exponent(S.brownian(16384, seed=s)) for s in range(6)]
    assert np.mean(alphas) == pytest.approx(1.0, abs=0.05)


@pytest.mark.parametrize("hurst", [0.35, 0.5, 0.75, 0.9])
def test_fractional_brownian_recovers_its_exponent(hurst):
    alphas = [msd_exponent(S.fractional_brownian(16384, hurst, seed=s)) for s in range(6)]
    assert np.mean(alphas) == pytest.approx(2 * hurst, abs=0.06)


def test_fractional_gaussian_noise_has_unit_variance_and_the_right_memory():
    """The scale matters as much as the exponent: a wrong one silences every amplitude test."""
    from soaring.analysis.observables.synthetic import _fgn

    hurst = 0.75
    series = np.array(
        [_fgn(2048, hurst, np.random.default_rng(s)) for s in range(120)]
    )
    assert series.var() == pytest.approx(1.0, abs=0.05)
    expected = 0.5 * (0 - 2 * 1 ** (2 * hurst) + 2 ** (2 * hurst))
    measured = np.mean([np.mean(x[:-1] * x[1:]) for x in series])
    assert measured == pytest.approx(expected, abs=0.03)


@pytest.mark.parametrize("alpha", [1.5, 1.8])
def test_levy_walk_has_a_ballistic_front(alpha):
    """A Lévy *walk* couples duration to distance, so its longest step is ballistic."""
    track = S.levy_walk(20000, alpha, seed=3)
    step = np.hypot(*np.diff(track, axis=0).T)
    assert step.max() > 0
    # Constant speed by construction: every within-leg step is the same length.
    assert np.median(step) == pytest.approx(12.0, rel=0.05)


def test_persistent_walk_crosses_over_at_its_own_timescale():
    track = S.persistent_walk(40000, 100.0, seed=1)
    assert msd_exponent(track, lo=4, hi=30) == pytest.approx(2.0, abs=0.15)
    assert msd_exponent(track, lo=2000, hi=15000) < 1.5


def test_with_drift_adds_a_ballistic_term():
    clean = S.brownian(8192, seed=0)
    drifted = S.with_drift(clean, (10.0, 0.0))
    assert msd_exponent(clean, lo=8, hi=512) == pytest.approx(1.0, abs=0.08)
    assert msd_exponent(drifted, lo=8, hi=512) > 1.7


@pytest.mark.parametrize("hurst", [0.7, 0.9])
def test_the_hosking_fallback_is_stationary_and_matches_the_exact_autocovariance(hurst):
    """The fallback path, checked against theory rather than against the fast path.

    Davies-Harte is exact and is what runs; Hosking is the fallback when the embedding is
    not non-negative definite, and it was updating the Durbin-Levinson coefficients in
    place. From order three the reflection step then reads entries the same loop has
    already overwritten, and the output stops being stationary fGn -- the variance drifted
    across the record. Nothing tested the fallback at all, which is how a generator error
    survives: an estimator validated against a broken generator is validated against the
    breakage.
    """
    from soaring.analysis.observables.synthetic import _fgn_hosking

    reps = 300
    sample = np.array([_fgn_hosking(256, hurst, np.random.default_rng(k)) for k in range(reps)])

    # Stationary: no drift in the variance from one end of the record to the other.
    assert sample[:, :20].var() == pytest.approx(1.0, abs=0.06)
    assert sample[:, -20:].var() == pytest.approx(1.0, abs=0.06)

    # And the right memory: gamma(k) = (|k+1|^2H - 2|k|^2H + |k-1|^2H) / 2.
    for k in range(1, 5):
        theory = 0.5 * (abs(k + 1) ** (2 * hurst) - 2 * abs(k) ** (2 * hurst) + abs(k - 1) ** (2 * hurst))
        measured = float(np.mean(sample[:, :-k] * sample[:, k:]))
        assert measured == pytest.approx(theory, abs=0.05)
