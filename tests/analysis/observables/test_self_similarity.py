"""Scaling oracles and uncertainty checks independent of the flight archive."""

import numpy as np
import pytest

from soaring.analysis.observables.self_similarity import (
    MOMENT_ORDERS,
    REFERENCE_RANGE,
    cdf_distance,
    excess_kurtosis,
    fit_moments,
    fit_quantiles,
    flight_power_means,
    measure_scaling,
    ordered_quantiles,
    paired_quantiles,
    positive_histogram,
    recover_positions,
    widest_windows,
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


def test_excess_kurtosis_matches_population_formula_for_equal_weights():
    from scipy.stats import kurtosis

    rng = np.random.default_rng(0)
    values = rng.standard_t(4, size=(500, 3))  # heavy-tailed: nonzero excess kurtosis
    owners = np.arange(500)
    sizes = np.ones(500)
    counts = np.ones((1, 500))
    result = excess_kurtosis(values, owners, sizes, counts)
    expected = kurtosis(values, axis=0, fisher=True, bias=True)
    np.testing.assert_allclose(result[0], expected, atol=1e-10)


def test_excess_kurtosis_replicates_whole_flight_bootstrap_draws():
    from scipy.stats import kurtosis

    # Same fixture shape as the paired-quantile bootstrap oracle above.
    values = np.array([[1.0], [2.0], [3.0], [10.0], [-5.0], [0.0]])
    owners = np.repeat(np.arange(3), 2)
    sizes = np.array([2, 2, 2.0])
    multiplicities = np.array([[1, 1, 1], [2, 0, 1], [0, 3, 0]])
    result = excess_kurtosis(values, owners, sizes, multiplicities)
    for j, counts_row in enumerate(multiplicities):
        replica = np.concatenate(
            [values[owners == f] for f in np.repeat(np.arange(3), counts_row)]
        )
        expected = kurtosis(replica, axis=0, fisher=True, bias=True)
        np.testing.assert_allclose(result[j], expected)


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


def test_one_exponent_flattens_the_spectrum_at_every_moment_order():
    lag = np.geomspace(10, 10000, 20)
    # An exactly self-similar law has <R^q> = C_q tau^(q H), one exponent per order.
    amplitudes = np.array([2.0, 5.0, 9.0])[None, :, None] ** MOMENT_ORDERS
    curves = (lag[:, None, None] / 1000) ** (0.81 * MOMENT_ORDERS) * amplitudes
    fitted = fit_moments(lag, curves, (10, 10000))
    np.testing.assert_allclose(fitted["nu"], 0.81, atol=1e-13)
    np.testing.assert_allclose(
        fitted["zeta"], np.tile(0.81 * MOMENT_ORDERS, (3, 1)), atol=1e-13
    )
    np.testing.assert_allclose(fitted["rms_log10"], 0, atol=1e-13)


def test_rank_dependent_exponents_bend_the_spectrum_towards_the_larger_branch():
    # Half the mass grows as tau^0.95, half as tau^0.80 from a much larger amplitude.
    # Every order weighs the branches by their size, so the spectrum falls monotonically
    # from a blend towards the exponent of the branch that carries the large values.
    lag = np.geomspace(60, 3000, 25)
    scale = lag[:, None] / 1000
    curves = (
        0.5 * (1.0 * scale**0.95) ** MOMENT_ORDERS
        + 0.5 * (40.0 * scale**0.80) ** MOMENT_ORDERS
    )[:, None, :]
    nu = fit_moments(lag, curves, (60, 3000))["nu"][0]
    assert np.all(np.diff(nu) < 0)
    assert 0.80 < nu[-1] < nu[0] < 0.95
    assert abs(nu[-1] - 0.80) < 0.01


def test_flight_power_means_average_within_flights_before_averaging_across_them():
    values = np.array([[1.0], [3.0], [10.0]])
    sizes = np.array([2, 1])
    means = flight_power_means(values, np.array([0, 2]), sizes, orders=(1.0, 2.0))
    np.testing.assert_allclose(means[:, 0, 0], [2.0, 10.0])
    np.testing.assert_allclose(means[:, 0, 1], [5.0, 100.0])
    # The equal-flight mixture halves the crowded flight's influence; pooling would not.
    assert means[:, 0, 0].mean() == 6.0
    assert values[:, 0].mean() != 6.0


def test_equal_flight_moments_replicate_whole_flight_bootstrap_draws():
    values = np.array([[1.0], [3.0], [10.0], [2.0], [6.0]])
    sizes = np.array([2, 1, 2])
    offsets = np.array([0, 2, 3])
    owners = np.repeat(np.arange(3), sizes)
    multiplicities = np.array([[1, 1, 1], [2, 0, 1], [0, 3, 0]])
    means = flight_power_means(values, offsets, sizes, orders=MOMENT_ORDERS)
    drawn = multiplicities @ means.reshape(3, -1) / multiplicities.sum(axis=1)[:, None]
    for d, counts in enumerate(multiplicities):
        replica = [values[owners == f, 0] for f in np.repeat(np.arange(3), counts)]
        expected = np.mean(
            [np.mean(flight[:, None] ** MOMENT_ORDERS, axis=0) for flight in replica],
            axis=0,
        )
        np.testing.assert_allclose(drawn[d], expected)


def test_widest_window_grows_with_the_tolerance_and_never_exceeds_the_scaling_range():
    lag = np.geomspace(10, 10000, 31)
    # Exponent 0.9 between two grid points, bending to 0.3 outside both knees.
    low, high = np.log10(lag[10]), np.log10(lag[23])
    x = np.log10(lag)
    logy = np.where(
        x < low,
        0.9 * low + 0.3 * (x - low),
        np.where(x > high, 0.9 * high + 0.3 * (x - high), 0.9 * x),
    )
    curves = (10**logy)[:, None, None]
    rows = widest_windows(lag, [curves], (0.002, 0.05))
    tight, loose = rows[0]["lags_s"], rows[1]["lags_s"]
    assert (tight[0], tight[1]) == (lag[10], lag[23])
    assert loose[1] / loose[0] > tight[1] / tight[0]
    assert rows[0]["worst_rms_log10"] <= 0.002
    # A curve that bends everywhere admits no window at a tolerance it cannot meet.
    bent = (10 ** (0.9 * x + 0.4 * x**2))[:, None, None]
    assert widest_windows(lag, [bent], (1e-6,))[0]["lags_s"] is None


def test_measured_spectrum_recovers_the_brownian_exponent_at_every_order():
    # Independent Gaussian steps on the 10 s grid scale as tau^0.5 at every order and
    # every rank, so the assembled estimator must return one exponent across the board.
    lags_s = np.array([10, 60, 110, 210, 390, 710, 1310, 2410, 2960, 4440, 10000])
    rng = np.random.default_rng(11)
    frames = [
        (
            {"flight_id": f, "segment_id": f, "duration_s": 25990},
            np.cumsum(rng.normal(size=(2600, 2)) * (1 + f), axis=0),
        )
        for f in range(5)
    ]
    result = measure_scaling(frames, lags_s, n_resamples=8)
    fit = result["fits"]["reference"]
    assert (fit["lags_s"][0], fit["lags_s"][-1]) == REFERENCE_RANGE
    assert result["moments_mq"].shape == (len(lags_s), 3, len(MOMENT_ORDERS))
    assert fit["nu_ci95"].shape == (2, 3, len(MOMENT_ORDERS))
    np.testing.assert_allclose(fit["nu"], 0.5, atol=0.06)
    np.testing.assert_allclose(fit["h"], 0.5, atol=0.06)
    # zeta(q) = q nu(q) is the same fit expressed per moment rather than per order.
    np.testing.assert_allclose(fit["zeta"], fit["nu"] * MOMENT_ORDERS, rtol=1e-12)
