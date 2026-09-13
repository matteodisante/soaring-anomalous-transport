"""Oracles for signs, temporal dependence, segment support and weighting."""

import numpy as np
import pytest

from soaring.analysis.observables.temporal_scaling import (
    cdf_features,
    fit_histogram_quantiles,
    magnitude_histograms,
    projection_directions,
    simultaneous_contrasts,
    two_increments,
)


def test_temporal_change_can_hide_from_every_coordinate_marginal():
    directions, _ = projection_directions()
    a = np.array([[1, 2, 1, 2], [-1, -2, -1, -2]], dtype=float)
    b = a.copy()
    b[:, 2:] *= -1
    fa, fb = (cdf_features(x, directions, [-1, 0, 1]) for x in (a, b))
    np.testing.assert_array_equal(fa[:4], fb[:4])
    np.testing.assert_array_equal(fa[[4, 5]], fb[[4, 5]])
    assert np.max(np.abs(fa - fb)) == 0.5


def test_exact_anisotropic_scaling_preserves_signed_temporal_cdfs():
    rng = np.random.default_rng(7)
    values = rng.normal(size=(1000, 4)) * [1, 3, 1, 3] + [1, -2, 1, -2]
    directions, _ = projection_directions()
    expected = cdf_features(values, directions, [-2, -0.5, 0, 0.5, 2])
    for lag in (10, 100, 1000):
        factor = (lag / 10) ** 0.73
        actual = cdf_features(
            values * factor / factor, directions, [-2, -0.5, 0, 0.5, 2]
        )
        np.testing.assert_array_equal(actual, expected)


def test_gap_is_never_a_temporal_neighbour():
    xy = np.column_stack((np.r_[np.arange(7), 100 + 2 * np.arange(7)], np.zeros(14)))
    row = {"segments": [[0, 7], [7, 14]]}
    one = two_increments(row, xy, 1, 2)
    two = two_increments(row, xy, 2, 2)
    assert one.shape == two.shape == (6, 4)
    np.testing.assert_array_equal(one[:, [0, 2]], [[1, 1]] * 3 + [[2, 2]] * 3)
    np.testing.assert_array_equal(two, one * 2)


def test_log_histogram_fit_has_bounded_quantisation_error():
    values = np.column_stack(
        (np.linspace(1, 9, 1001), np.linspace(2, 10, 1001), np.zeros((1001, 2)))
    )
    edges = np.geomspace(1e-6, 1e7, 8193)
    lags = [10, 100, 1000]
    hist = np.array(
        [magnitude_histograms(values * (lag / 10) ** 0.71, edges) for lag in lags]
    )
    fit = fit_histogram_quantiles(hist, edges, lags, [0.25, 0.5, 0.75, 0.9])
    assert (
        np.max(np.abs(np.array(fit["slopes"]) - 0.71))
        <= fit["h_absolute_resolution_bound"]
    )


def test_paired_cluster_resampling_preserves_equal_flight_weights():
    # Unequal date sizes. The same CDF on each lag makes every paired contrast zero.
    sums = np.array([[[[0.0]], [[0.0]]], [[[9.0]], [[9.0]]]])
    mean, contrasts, radius, errors = simultaneous_contrasts(
        sums, [1, 9], resamples=50, seed=2
    )
    np.testing.assert_array_equal(mean, 0.9)
    np.testing.assert_array_equal(contrasts, 0)
    assert radius == 0
    np.testing.assert_array_equal(errors, 0)


def test_cdf_includes_exact_zero_atoms():
    assert (
        cdf_features(np.zeros((5, 4)), np.eye(4), [-1, 0, 1]).tolist()
        == [[0, 1, 1]] * 4
    )


def test_training_quantile_underflow_is_rejected():
    edges = np.geomspace(1e-6, 1e7, 8193)
    hist = np.array([magnitude_histograms(np.zeros((3, 4)), edges)] * 3)
    with pytest.raises(ValueError, match="outside"):
        fit_histogram_quantiles(hist, edges, [10, 100, 1000], [0.5])
