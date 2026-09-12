"""Scaling oracles and uncertainty checks independent of the flight archive."""

import numpy as np
import pytest

from soaring.analysis.observables.self_similarity import (
    cdf_distance,
    fit_quantiles,
    ordered_quantiles,
    paired_quantiles,
    positive_histogram,
    recover_positions,
)


def test_one_scale_can_be_anisotropic_and_squares_double_every_slope():
    lag = np.geomspace(10, 10000, 20)
    # Fixed anisotropy and four different rank amplitudes share one time scale.
    curves = (
        (lag[:, None, None] / 1000) ** 0.73
        * np.array([1, 3, 4])[None, :, None]
        * np.array([2, 4, 7, 10])
    )
    fitted = fit_quantiles(lag, curves, (10, 10000))
    squared = fit_quantiles(lag, curves**2, (10, 10000))
    np.testing.assert_allclose(fitted["h"], 0.73, atol=1e-13)
    np.testing.assert_allclose(fitted["common_rms_log10"], 0, atol=1e-13)
    np.testing.assert_allclose(squared["h"], 1.46, atol=1e-13)


def test_different_rank_exponents_fail_the_common_scale_fit():
    lag = np.geomspace(10, 10000, 20)
    exponents = np.array([0.7, 0.8, 0.9, 1.0])
    curves = lag[:, None, None] ** exponents * np.ones((1, 3, 1))
    fitted = fit_quantiles(lag, curves, (10, 10000))
    np.testing.assert_allclose(fitted["h"], np.tile(exponents, (3, 1)))
    assert np.min(fitted["common_rms_log10"]) > 0.09


def test_equal_flight_bootstrap_recomputes_pooled_quantiles_not_mean_quantile():
    # Equal origins per flight allow a simple explicit replication oracle.
    values = np.array([[1, 7], [1, 8], [2, 20], [100, 30], [3, 60], [4, 70.0]])
    owners = np.repeat(np.arange(3), 2)
    multiplicities = np.array([[1, 1, 1], [2, 0, 1], [0, 3, 0]])
    result = paired_quantiles(values, owners, multiplicities)
    for j, counts in enumerate(multiplicities):
        replica = np.concatenate(
            [values[owners == f] for f in np.repeat(np.arange(3), counts)]
        )
        expected = np.quantile(
            replica, [0.25, 0.5, 0.75, 0.9], axis=0, method="inverted_cdf"
        ).T
        np.testing.assert_array_equal(result[j], expected)
    assert result[0, 0, 1] == 2


def test_flights_with_unequal_origins_still_have_equal_total_mass():
    values = np.array([[1.0], [2.0], [3.0], [100.0]])
    result = paired_quantiles(values, np.array([0, 0, 0, 1]), np.array([[1, 1]]))
    np.testing.assert_array_equal(result[0, 0], [2, 3, 100, 100])
    assert (
        ordered_quantiles(
            np.array([1, 2, 3, 100]), np.array([1 / 3, 1 / 3, 1 / 3, 1.0]), [0.5]
        )[0]
        == 3
    )


def test_squared_histogram_preserves_probability_and_cdf_distance():
    x = np.array([0, 0.1, 0.5, 1, 2, 5.0])
    y = np.array([0, 0.2, 0.4, 2, 3, 6.0])
    weights = np.array([1, 2, 1, 2, 1, 1.0])
    edges = np.array([0.01, 0.4, 0.9, 3, 10.0])
    mass, atom = positive_histogram(x, weights, edges)
    squared_mass, squared_atom = positive_histogram(x**2, weights, edges**2)
    np.testing.assert_array_equal(mass, squared_mass)
    assert atom == squared_atom == 0.125
    assert np.sum((mass / np.diff(edges**2)) * np.diff(edges**2)) + atom == 1
    assert cdf_distance(x, weights, y, weights) == cdf_distance(
        x**2, weights, y**2, weights
    )
    assert cdf_distance(x, weights, x * 8 / 8, weights) == 0
    with pytest.raises(ValueError, match="omit"):
        positive_histogram(x, weights, np.array([0.4, 1, 3]))


def test_reconstruction_rejects_missing_increments():
    import pandas as pd

    measured = {
        "frame": pd.DataFrame([{"duration_s": 30}]),
        "owners": [np.array([0, 0])],
        "vectors": [np.ones((2, 2))],
    }
    with pytest.raises(ValueError, match="complete segment"):
        recover_positions(measured, [10, 20])
    measured["frame"]["duration_s"] = 20
    frames = recover_positions(measured, [10, 20])
    np.testing.assert_array_equal(frames[0][1], [[0, 0], [1, 1], [2, 2]])


def test_unchanged_marginals_do_not_fix_the_radial_distribution():
    # Same component empirical laws, different pairing of their large values.
    paired = np.array([[1, 1], [1, 1], [3, 3], [3, 3.0]])
    crossed = np.array([[1, 3], [1, 3], [3, 1], [3, 1.0]])
    weights = np.ones(4)
    for k in range(2):
        assert cdf_distance(paired[:, k], weights, crossed[:, k], weights) == 0
    assert (
        cdf_distance(
            np.linalg.norm(paired, axis=1),
            weights,
            np.linalg.norm(crossed, axis=1),
            weights,
        )
        == 0.5
    )
