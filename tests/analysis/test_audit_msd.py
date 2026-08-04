"""The audit's copy of the coverage rule must agree with the estimator's original.

``scripts/reporting/audit_msd.py`` deliberately duplicates
:class:`soaring.analysis.transport.MSDAccumulator`'s coverage rule instead of importing
it, so that a change to the estimator shows up as a disagreement between the figure and
the audit rather than being tracked silently. A duplicate that nobody compares is just a
second implementation waiting to drift, so the comparison is this file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from soaring.analysis.transport import MSDAccumulator

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit():
    return _load("audit_msd", "scripts/reporting/audit_msd.py")


@pytest.fixture(scope="module")
def report():
    return _load("audit_msd_report", "scripts/reporting/audit_msd_report.py")


def _flight(step: float, n: int, seed: int):
    """A random-walk flight on a uniform grid of the given step, starting at the origin."""
    rng = np.random.default_rng(seed)
    times = np.arange(n, dtype=float) * step
    east = np.concatenate([[0.0], np.cumsum(rng.normal(0, 5.0, n - 1))])
    north = np.concatenate([[0.0], np.cumsum(rng.normal(0, 5.0, n - 1))])
    return times, east, north


@pytest.mark.parametrize("step", [1.0, 2.0, 5.0, 10.0])
def test_audit_coverage_matches_the_estimator(audit, step):
    """Same lags covered, same |r|^2 where covered, for every common cadence."""
    lags = np.unique(np.round(np.geomspace(1.0, 4000.0, 60)))
    times, east, north = _flight(step, 600, seed=int(step))

    accumulator = MSDAccumulator(lags)
    accumulator.add(times, east, north)
    from_estimator = accumulator.stacked_samples()[0]

    sampled_e, sampled_n, native = audit._sample_flight(times, east, north, lags)
    from_audit = sampled_e.astype(float) ** 2 + sampled_n.astype(float) ** 2

    assert native == pytest.approx(step)
    np.testing.assert_array_equal(np.isnan(from_estimator), np.isnan(from_audit))
    covered = ~np.isnan(from_audit)
    np.testing.assert_allclose(
        from_estimator[covered], from_audit[covered], rtol=1e-5, atol=1e-3
    )


def test_audit_refuses_lags_below_the_native_step(audit):
    """A slow logger abstains at short lags instead of answering with its fix at t = 0."""
    lags = np.array([1.0, 2.0, 5.0, 10.0, 20.0])
    times, east, north = _flight(10.0, 50, seed=7)
    sampled_e, _, _ = audit._sample_flight(times, east, north, lags)
    assert np.isnan(sampled_e[lags < 10.0]).all()
    assert not np.isnan(sampled_e[lags >= 10.0]).any()


def test_power_law_residual_is_zero_on_a_power_law(report):
    """The residual is what decides whether an exponent describes a curve."""
    t = np.geomspace(1.0, 1000.0, 50)
    alpha, residual = report.power_law_residual(t, 3.0 * t**1.7)
    assert alpha == pytest.approx(1.7)
    assert residual == pytest.approx(0.0, abs=1e-12)


def test_power_law_residual_sees_a_crossover(report):
    """A curve that bends leaves a residual an exponent alone would not report."""
    t = np.geomspace(1.0, 1000.0, 50)
    bent = np.where(t < 100.0, t**1.2, 100.0 ** (1.2 - 2.0) * t**2.0)
    _, residual = report.power_law_residual(t, bent)
    assert residual > 0.05


def test_local_slope_recovers_a_power_law(report):
    """d log y / d log t is the exponent, away from the ends of the grid."""
    t = np.geomspace(1.0, 10_000.0, 90)
    slopes = report.local_slope(t, 2.0 * t**1.4)
    inner = np.isfinite(slopes)
    np.testing.assert_allclose(slopes[inner], 1.4, atol=1e-6)
