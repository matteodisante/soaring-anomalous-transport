"""Tests for the altitude-noise diagnostics: sample-size stats and PSD aggregation."""

import math

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.altitude_noise import (
    _Accumulator,
    _uniform_resample,
    baro_presence_from_scan,
    proportion_ci,
    required_sample_size,
)

# norm.ppf(0.975): the two-sided 95% standard-normal quantile, computed
# independently of the module so the assertions below are not tautological.
Z95 = 1.959963984540054


# --------------------------------------------------------------------------- #
# baro presence (census from an already-parsed scan)
# --------------------------------------------------------------------------- #
def test_baro_presence_from_scan_counts_absent():
    # BARO_PRESENT_MIN = 0.5: the two flights at 0.0 and 0.1 count as absent.
    scan = pd.DataFrame({"baro_present_frac": [1.0, 0.0, 0.9, 0.1, 0.6]})
    absent, n = baro_presence_from_scan(scan)
    assert n == 5
    assert absent == 2


def test_baro_presence_from_scan_all_present():
    scan = pd.DataFrame({"baro_present_frac": [1.0, 0.95, 0.8]})
    absent, n = baro_presence_from_scan(scan)
    assert absent == 0
    assert n == 3


# --------------------------------------------------------------------------- #
# required_sample_size: n = z^2 p(1-p) / e^2
# --------------------------------------------------------------------------- #
def test_required_sample_size_textbook_value():
    # 95% confidence, margin +/-2 pp, conservative p=0.5 -> the classic n = 2401.
    assert required_sample_size(0.02) == 2401


def test_required_sample_size_monotone_in_margin():
    # Tighter precision demands a larger sample.
    assert (
        required_sample_size(0.01)
        > required_sample_size(0.02)
        > required_sample_size(0.05)
    )


def test_required_sample_size_p_half_is_conservative():
    # p=0.5 maximises the variance bound, so it returns the largest n over any p.
    n_half = required_sample_size(0.02, p=0.5)
    for p in (0.1, 0.3, 0.7, 0.9):
        assert required_sample_size(0.02, p=p) <= n_half


def test_required_sample_size_grows_with_confidence():
    assert required_sample_size(0.02, confidence=0.99) > required_sample_size(
        0.02, confidence=0.95
    )


# --------------------------------------------------------------------------- #
# proportion_ci: (p_hat, half_width) with half_width = z*sqrt(p(1-p)/n)
# --------------------------------------------------------------------------- #
def test_proportion_ci_point_estimate_and_width():
    p_hat, hw = proportion_ci(50, 100)
    assert p_hat == 0.5
    # z * sqrt(0.25 / 100) = z * 0.05
    assert hw == pytest.approx(Z95 * 0.05)


def test_proportion_ci_zero_sample_is_nan():
    p_hat, hw = proportion_ci(0, 0)
    assert p_hat == 0.0
    assert math.isnan(hw)


def test_proportion_ci_exact_census_has_zero_width():
    # p_hat at 0 or 1 -> variance 0 -> zero-width interval.
    assert proportion_ci(0, 100) == (0.0, 0.0)
    assert proportion_ci(100, 100) == (1.0, 0.0)


# --------------------------------------------------------------------------- #
# _uniform_resample: linear interpolation onto a uniform grid of step dt
# --------------------------------------------------------------------------- #
def test_uniform_resample_ramp_is_exact():
    t = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    out = _uniform_resample(t, 2.0 * t, 1.0)
    assert np.allclose(out, [0.0, 2.0, 4.0, 6.0, 8.0])


def test_uniform_resample_finer_grid_interpolates_linearly():
    t = np.array([0.0, 2.0, 4.0])
    z = np.array([0.0, 4.0, 8.0])  # slope 2
    out = _uniform_resample(t, z, 1.0)  # grid 0,1,2,3,4
    assert np.allclose(out, [0.0, 2.0, 4.0, 6.0, 8.0])


def test_uniform_resample_grid_endpoints_and_length():
    t = np.array([0.0, 1.0, 2.0, 3.0])
    out = _uniform_resample(t, t.copy(), 0.5)  # arange(0, 3.25, 0.5) -> 7 points
    assert len(out) == 7
    assert out[0] == t[0]
    assert np.isclose(out[-1], t[-1])


def test_uniform_resample_identity_on_uniform_input():
    t = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    z = np.array([5.0, 3.0, 9.0, 1.0, 7.0])
    assert np.allclose(_uniform_resample(t, z, 1.0), z)


# --------------------------------------------------------------------------- #
# _Accumulator: per-(discipline, channel) PSD ensemble reductions
# --------------------------------------------------------------------------- #
def _fill(acc, disc, channel, curves, f=None):
    f = np.array([0.0, 1.0, 2.0]) if f is None else f
    for c in curves:
        acc.add_psd(disc, channel, f, np.asarray(c, dtype=float))
    return f


def test_accumulator_median_is_robust_where_mean_is_not():
    # The design rationale made executable: four typical flights + one artefact
    # flight. The per-frequency median ignores the outlier; the mean is dragged up.
    acc = _Accumulator()
    _fill(acc, "para", "baro", [[1, 1, 1]] * 4 + [[100, 100, 100]])
    _, med = acc.median_psd("para", "baro")
    _, mean = acc.mean_psd("para", "baro")
    assert np.allclose(med, 1.0)  # robust: unaffected by the single spike
    assert np.all(mean > 15.0)  # mean of [1,1,1,1,100] = 20.8


def test_accumulator_band_psd_returns_percentiles():
    acc = _Accumulator()
    curves = [[v, v] for v in (1, 2, 3, 4, 5)]
    f = _fill(acc, "para", "gnss", curves, f=np.array([0.0, 1.0]))
    fout, plo, pmed, phi = acc.band_psd("para", "gnss", lo=10.0, hi=90.0)
    assert np.allclose(fout, f)
    assert np.allclose(pmed, 3.0)  # median of 1..5
    assert np.allclose(plo, 1.4)  # 10th percentile (linear interpolation)
    assert np.allclose(phi, 4.6)  # 90th percentile


def test_accumulator_pooled_band_psd_pools_channel_across_disciplines():
    acc = _Accumulator()
    f = np.array([0.0, 1.0])
    acc.add_psd("para", "gnss", f, np.array([1.0, 1.0]))
    acc.add_psd("delta", "gnss", f, np.array([3.0, 3.0]))
    acc.add_psd("para", "baro", f, np.array([100.0, 100.0]))  # other channel: excluded
    _, _, pmed, _ = acc.pooled_band_psd("gnss")
    # median of the two gnss curves [1, 3]; if baro leaked in it would be 3.
    assert np.allclose(pmed, 2.0)


def test_accumulator_drops_curves_off_the_common_grid():
    acc = _Accumulator()
    acc.add_psd("para", "baro", np.array([0.0, 1.0, 2.0]), np.array([1.0, 1.0, 1.0]))
    assert acc.n_psd("para", "baro") == 1
    # a curve on a different-length grid cannot be pooled -> silently dropped
    acc.add_psd("para", "baro", np.array([0.0, 1.0, 2.0, 3.0]), np.array([9.0] * 4))
    assert acc.n_psd("para", "baro") == 1
    _, med = acc.median_psd("para", "baro")
    assert len(med) == 3 and np.allclose(med, 1.0)


def test_accumulator_empty_reductions_are_none():
    acc = _Accumulator()
    assert acc.n_psd("para", "baro") == 0
    assert acc.median_psd("para", "baro") is None
    assert acc.mean_psd("para", "baro") is None
    assert acc.band_psd("para", "baro") is None
    assert acc.pooled_band_psd("baro") is None
