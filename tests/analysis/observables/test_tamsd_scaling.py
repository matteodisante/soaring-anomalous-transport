"""Cluster uncertainty for effective exponents of equal-flight TAMSD curves."""

import numpy as np
import pytest

from soaring.analysis.observables.tamsd_scaling import (
    clustered_scaling_summary,
    fit_loglog,
)


def test_perfect_power_law_has_expected_exponents_in_each_window():
    lags = np.geomspace(10, 10000, 31)
    values = np.tile(3 * lags**1.7, (24, 2, 1))
    values[:, 1] *= 2
    result = clustered_scaling_summary(
        values, np.arange(24), lags, control_names=["all", "long"], resamples=48
    )
    assert len(result["fits"]) == 6
    for record in result["fits"]:
        assert record["status"] == "ok"
        assert record["h_eff"] == pytest.approx(0.85)
        assert record["slope"] == pytest.approx(1.7)
        expected_amplitude = 3 if record["control"] == "all" else 6
        assert np.exp(record["intercept_log_m2"]) == pytest.approx(expected_amplitude)
        np.testing.assert_allclose(record["h_eff_percentile_95"], [0.85, 0.85])
        assert record["h_eff_bootstrap_se"] < 1e-14
        assert record["n_finite_resamples"] == 48
        assert record["n_flights_min"] == record["n_clusters_min"] == 24


def test_between_cluster_shapes_have_uncertainty_despite_exact_aggregate_fit():
    lags = np.geomspace(10, 100, 11)
    base = 7 * lags**1.6
    perturbation = 0.6 * np.linspace(-1, 1, len(lags))
    values = np.stack([base * (1 + perturbation), base * (1 - perturbation)])
    values = np.repeat(values, 12, axis=0)[:, None, :]
    result = clustered_scaling_summary(
        values, np.arange(24), lags, intervals=((10, 100),), resamples=400
    )
    record = result["fits"][0]
    np.testing.assert_allclose(result["mean_m2"][0], base)
    assert record["h_eff"] == pytest.approx(0.8)
    assert record["h_eff_bootstrap_se"] > 0.01
    low, high = record["h_eff_percentile_95"]
    assert low < 0.8 < high


def test_amplitude_only_variation_has_curve_uncertainty_but_constant_exponent():
    lags = np.geomspace(10, 100, 7)
    amplitudes = np.geomspace(1, 100, 24)
    values = amplitudes[:, None, None] * lags[None, None, :] ** 1.4
    result = clustered_scaling_summary(
        values, np.arange(24), lags, intervals=((10, 100),), resamples=200
    )
    record = result["fits"][0]
    assert record["h_eff"] == pytest.approx(0.7)
    assert record["h_eff_bootstrap_se"] < 1e-14
    np.testing.assert_allclose(record["h_eff_percentile_95"], [0.7, 0.7])
    assert np.all(result["pointwise_95_m2"][0] < result["pointwise_95_m2"][1])


def test_unequal_cluster_sizes_keep_equal_flight_weights_and_paired_controls():
    lags = np.array([10.0, 30.0, 100.0])
    group_sizes = 1 + np.arange(24) % 4
    amplitudes = np.arange(1.0, 25.0)
    labels = np.repeat(np.arange(24), group_sizes)
    flight_amplitudes = amplitudes[labels]
    curves = lags[None, :] ** (1.2 + amplitudes[:, None] / 50)
    values = curves[labels, None, :] * flight_amplitudes[:, None, None]
    values = np.concatenate([values, 2 * values], axis=1)
    seed, resamples = 92, 96
    result = clustered_scaling_summary(
        values,
        labels,
        lags,
        intervals=((10, 100),),
        seed=seed,
        resamples=resamples,
    )
    expected_mean = (group_sizes[:, None] * amplitudes[:, None] * curves).sum(
        axis=0
    ) / group_sizes.sum()
    np.testing.assert_allclose(result["mean_m2"][0], expected_mean)
    # Independently reconstruct complete-cluster draws and their flight weights.
    draws = np.random.default_rng(seed).multinomial(
        24, np.full(24, 1 / 24), size=resamples
    )
    bootstrap_curves = (
        draws @ (group_sizes[:, None] * amplitudes[:, None] * curves)
    ) / (draws @ group_sizes)[:, None]
    expected_bounds = np.quantile(bootstrap_curves, [0.025, 0.975], axis=0)
    np.testing.assert_allclose(result["pointwise_95_m2"][:, 0], expected_bounds)
    np.testing.assert_allclose(result["pointwise_95_m2"][:, 1], 2 * expected_bounds)
    bootstrap_slopes, _ = fit_loglog(lags, bootstrap_curves)
    first, second = result["fits"]
    np.testing.assert_allclose(
        first["h_eff_percentile_95"], np.quantile(bootstrap_slopes / 2, [0.025, 0.975])
    )
    np.testing.assert_allclose(
        first["h_eff_percentile_95"], second["h_eff_percentile_95"]
    )
    assert first["h_eff_bootstrap_se"] == pytest.approx(second["h_eff_bootstrap_se"])
    assert result["n_flights"].min() == group_sizes.sum()
    assert result["n_clusters"].min() == len(group_sizes)


def test_support_selection_is_fixed_and_small_cluster_counts_suppress_intervals():
    lags = np.array([10, 20, 40, 80, 100])
    values = np.tile(lags**1.2, (24, 1, 1))
    values[:, :, 3] = -1  # A nonpositive mean cannot enter a logarithmic fit.
    values[7:, :, 4] = np.nan  # Seven flights cannot define the fitted grid.
    result = clustered_scaling_summary(
        values, np.arange(24), lags, intervals=((10, 100),), resamples=48
    )
    record = result["fits"][0]
    np.testing.assert_array_equal(record["actual_lags_s"], [10, 20, 40])
    assert record["h_eff"] == pytest.approx(0.6)
    assert record["status"] == "ok"
    assert record["n_lags"] == 3
    assert np.isnan(result["pointwise_95_m2"][:, 0, -1]).all()
    clustered = clustered_scaling_summary(
        values, np.repeat(np.arange(12), 2), lags, resamples=48
    )
    assert clustered["fits"][0]["h_eff"] == pytest.approx(0.6)
    assert clustered["fits"][0]["status"] == "insufficient_clusters"
    assert np.isnan(clustered["fits"][0]["h_eff_percentile_95"]).all()
    assert np.isnan(clustered["fits"][0]["h_eff_bootstrap_se"])
    assert np.isnan(clustered["pointwise_95_m2"]).all()
    assert clustered["fits"][1]["status"] == "insufficient_flight_support"


def test_missing_bootstrap_lags_cannot_shrink_grid_to_obtain_a_fit():
    lags = np.array([10, 20, 100])
    values = np.tile(lags**1.2, (24, 1, 1))
    values[1:, :, -1] = np.nan
    result = clustered_scaling_summary(
        values,
        np.arange(24),
        lags,
        intervals=((10, 100),),
        min_flights=1,
        min_clusters=1,
        resamples=300,
    )
    record = result["fits"][0]
    assert record["h_eff"] == pytest.approx(0.6)
    np.testing.assert_array_equal(record["actual_lags_s"], lags)
    assert record["status"] == "insufficient_finite_resamples"
    assert 0 < record["n_finite_resamples"] < 0.9 * 300
    assert np.isnan(record["h_eff_percentile_95"]).all()
    assert np.isnan(record["h_eff_bootstrap_se"])
    slopes, _ = fit_loglog(lags, [[1, 4, np.nan], [1, 4, 0], [1, 4, np.inf]])
    assert np.isnan(slopes).all()


def test_empty_and_insufficient_support_are_explicit():
    result = clustered_scaling_summary(np.empty((0, 2, 3)), [], [10, 20, 100])
    assert result["resamples"] == 2000
    assert result["seed"] == 20260915
    assert result["support_rules"]["min_flights"] == 8
    assert np.isnan(result["mean_m2"]).all()
    assert np.isnan(result["pointwise_95_m2"]).all()
    assert not result["n_flights"].any()
    assert not result["n_clusters"].any()
    assert result["n_clusters_total"] == 0
    assert len(result["fits"]) == 6
    for record in result["fits"]:
        assert record["status"] == "insufficient_flight_support"
        assert np.isnan(record["h_eff"])
        assert record["n_lags"] == 0
    no_support = clustered_scaling_summary(
        np.full((24, 1, 3), np.inf), np.arange(24), [10, 20, 100], resamples=20
    )
    assert np.isnan(no_support["mean_m2"]).all()
    assert no_support["fits"][0]["status"] == "insufficient_flight_support"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"labels": [0]},
        {"lags": [1, 1, 2]},
        {"lags": [0, 1, 2]},
        {"resamples": 1},
        {"min_finite_fraction": 0},
        {"control_names": ["one", "two"]},
    ],
)
def test_misaligned_or_invalid_arguments_fail_clearly(kwargs):
    arguments = {
        "values": np.ones((24, 1, 3)),
        "labels": np.arange(24),
        "lags": [1, 2, 3],
    }
    arguments.update(kwargs)
    with pytest.raises(ValueError):
        clustered_scaling_summary(**arguments)
