"""Calendar geometry, estimator preservation and known dependence controls."""

import numpy as np
import pytest

from soaring.analysis.observables.bootstrap_reliability import (
    block_support,
    boundary_offsets,
    calendar_blocks,
    diagnostic_statistics,
    uncertainty_summary,
)
from soaring.analysis.observables.fixed_bootstrap import bootstrap_means, cluster_draws


def test_calendar_blocks_preserve_empty_days_years_and_shared_dates():
    dates = [
        "2000-01-01",
        "2000-01-01",
        "2000-01-02",
        "2000-01-04",
        "2001-01-01",
        None,
        "0000-00-00",
    ]
    labels, missing = calendar_blocks(dates, 2)
    np.testing.assert_array_equal(labels, [0, 0, 0, 1, 2, 3, 4])
    np.testing.assert_array_equal(missing, [False] * 5 + [True, True])
    shifted, _ = calendar_blocks(dates, 2, offset=1)
    assert shifted[0] != shifted[2]
    # Missing calendar days cannot be compressed into adjacent observed dates.
    labels, _ = calendar_blocks(["2000-01-01", "2000-01-08"], 4)
    assert labels[0] != labels[1]


@pytest.mark.parametrize("days,offset", [(0, 0), (-1, 0), (2, -1), (2, 2), (1.5, 0)])
def test_invalid_block_definition_fails(days, offset):
    with pytest.raises(ValueError):
        calendar_blocks(["2000-01-01"], days, offset)


def test_boundary_shifts_and_nested_anchor_partitions():
    assert boundary_offsets(1) == [0]
    assert boundary_offsets(2) == [0, 1]
    assert boundary_offsets(8) == [0, 2, 5]
    dates = np.arange("2000-01-01", "2000-02-01", dtype="datetime64[D]").astype(str)
    fine, _ = calendar_blocks(dates, 2)
    coarse, _ = calendar_blocks(dates, 4)
    for group in np.unique(fine):
        assert len(np.unique(coarse[fine == group])) == 1


def test_size_balance_counts_only_contributing_flights():
    result = block_support([0, 0, 0, 1, 2, 2], [True, True, True, True, False, False])
    assert result["archive_blocks"] == 3
    assert result["contributing_blocks"] == 2
    assert result["largest_block_fraction"] == 0.75
    assert result["size_balance_index"] == pytest.approx(1.6)


def test_equal_flight_mean_and_fit_use_whole_paired_curves():
    lags = np.array([10, 100, 1000, 10000])
    exponents = np.array([0.8, 1.1, 1.3])
    values = lags[None, :] ** exponents[:, None]
    curves = bootstrap_means(values, [0, 0, 1], np.array([[1, 1], [2, 0], [0, 2]]))
    stats = diagnostic_statistics(lags, curves)
    np.testing.assert_allclose(stats[0, :3], values.mean(axis=0)[1:])
    assert stats[0, -1] != pytest.approx(exponents.mean() / 2)
    assert stats[2, -1] == pytest.approx(0.65)
    # Resampling a two-flight block must preserve their separate flight weights.
    np.testing.assert_allclose(stats[1, :3], values[:2].mean(axis=0)[1:])


def test_uncertainty_omits_observed_row_and_reports_missing_replicates():
    values = np.tile([999, 1, 2, 3, np.nan], (4, 1)).T
    result = uncertainty_summary(values)["hurst"]
    assert result["point"] == 999
    assert result["se"] == pytest.approx(1)
    assert result["low"] == pytest.approx(1.1)
    assert result["high"] == pytest.approx(2.9)
    assert result["valid_replicates"] == 3
    assert result["invalid_replicates"] == 1


def test_shared_daily_shock_inflates_se_by_expected_factor():
    # Eight perfectly dependent flights per day: treating them as independent
    # underestimates variance by about eight, hence SE by sqrt(8).
    rng = np.random.default_rng(410)
    daily = rng.normal(size=300)
    values = np.repeat(daily, 8)[:, None]
    separate = np.arange(len(values))
    together = np.repeat(np.arange(len(daily)), 8)
    naive = bootstrap_means(values, separate, cluster_draws(separate, 1500, 11))[1:, 0]
    blocked = bootstrap_means(values, together, cluster_draws(together, 1500, 12))[
        1:, 0
    ]
    ratio = np.std(blocked, ddof=1) / np.std(naive, ddof=1)
    assert ratio == pytest.approx(np.sqrt(8), rel=0.08)


def test_daily_contributions_keep_flight_weights_and_calendar_gaps():
    from soaring.analysis.observables.bootstrap_reliability import daily_contributions

    calendar, daily, counts, _ = daily_contributions(
        ["2000-01-01", "2000-01-01", "2000-01-03"], [[1], [3], [-4]]
    )
    assert len(calendar) == 3
    np.testing.assert_array_equal(counts, [2, 0, 1])
    np.testing.assert_array_equal(daily[:, 0], [4, 0, -4])
    # Averaging daily means would change the equal-flight estimator.
    assert daily.sum() == 0


def test_month_centring_is_pooled_across_years_and_weighted_by_flights():
    from soaring.analysis.observables.bootstrap_reliability import daily_contributions

    dates = ["2000-01-01", "2000-01-01", "2001-01-01", "2000-02-01"]
    _, daily, counts, monthly = daily_contributions(
        dates, [[0], [2], [4], [10]], centre_months=True
    )
    assert monthly[0, 0] == 2
    assert monthly[1, 0] == 10
    assert daily[0, 0] == -2
    assert daily[-1, 0] == 2
    assert daily.sum() == 0
    assert counts.sum() == 4


def test_h_influence_matches_perturbing_the_population_curve():
    from soaring.analysis.observables.bootstrap_reliability import diagnostic_influence

    lags = np.array([10, 100, 1000, 10000])
    values = np.array([1, 2, 3])[:, None] * lags ** np.array([1.1, 1.5, 1.8])[:, None]
    scores = diagnostic_influence(lags, values)
    np.testing.assert_allclose(scores.sum(axis=0), 0, atol=1e-14)
    eps = 1e-5
    mean = values.mean(axis=0)
    direction = values[0] - mean
    curves = np.stack([mean - eps * direction, mean + eps * direction])
    derivative = np.diff(diagnostic_statistics(lags, curves), axis=0)[0] / (2 * eps)
    np.testing.assert_allclose(derivative[:3] / mean[1:], scores[0, :3], rtol=1e-7)
    assert derivative[-1] == pytest.approx(scores[0, -1], rel=1e-7)


def test_daily_covariance_uses_actual_day_distances():
    from soaring.analysis.observables.bootstrap_reliability import daily_correlogram

    result = daily_correlogram([[4], [0], [-4]], [2, 0, 1], 2)
    np.testing.assert_allclose(result["rho"][:, 0], [1, 0, -0.5])
    np.testing.assert_array_equal(result["occupied_pairs"], [2, 0, 1])
    assert result["variance_factor"][2, 0] == 1


def test_bartlett_factor_matches_sums_of_overlapping_blocks():
    from soaring.analysis.observables.bootstrap_reliability import daily_correlogram

    daily = np.array([1, 3, -2, 4, -1, -5], dtype=float)
    length = 4
    result = daily_correlogram(daily[:, None], np.ones(len(daily)), length)
    block_sums = np.convolve(daily, np.ones(length), mode="full")
    expected = np.sum(block_sums**2) / (length * np.sum(daily**2))
    assert result["variance_factor"][length, 0] == pytest.approx(expected)


def test_known_ar1_daily_dependence_and_independent_control():
    from soaring.analysis.observables.bootstrap_reliability import daily_correlogram

    rng = np.random.default_rng(100)
    noise = rng.normal(size=30000)
    correlated = noise.copy()
    phi = 0.7
    for i in range(1, len(noise)):
        correlated[i] += phi * correlated[i - 1]
    daily = np.column_stack([noise, correlated])
    daily -= daily.mean(axis=0)
    result = daily_correlogram(daily, np.ones(len(daily)), 32)
    np.testing.assert_allclose(result["rho"][1:5, 0], 0, atol=0.025)
    np.testing.assert_allclose(
        result["rho"][1:5, 1], phi ** np.arange(1, 5), atol=0.025
    )
    theoretical = 1 + 2 * np.sum((1 - np.arange(1, 32) / 32) * phi ** np.arange(1, 32))
    assert result["variance_factor"][32, 0] == pytest.approx(1, abs=0.12)
    assert result["variance_factor"][32, 1] == pytest.approx(theoretical, rel=0.1)


def test_daily_diagnostic_rejects_missing_dates_and_degenerate_series():
    from soaring.analysis.observables.bootstrap_reliability import (
        daily_contributions,
        daily_correlogram,
    )

    with pytest.raises(ValueError, match="valid date"):
        daily_contributions(["0000-00-00"], [[1]])
    with pytest.raises(ValueError, match="nonzero daily variation"):
        daily_correlogram(np.zeros((5, 1)), np.ones(5), 2)
    with pytest.raises(ValueError, match="within the calendar"):
        daily_correlogram(np.ones((5, 1)), np.ones(5), 5)
