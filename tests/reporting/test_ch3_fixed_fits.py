"""Matched-range cohort slopes retain paired uncertainty and measured lag support."""

import runpy
from pathlib import Path

import numpy as np

MODULE = runpy.run_path(
    str(
        Path(__file__).resolve().parents[2]
        / "scripts/reporting/ch3_global_transport/summarize_ch3_fixed.py"
    )
)


def test_cohort_contrasts_use_shared_lags_and_paired_replicates():
    lags = np.array([10, 20, 40, 100, 200, 400, 1000, 10000])
    shared_slope_noise = np.array([0, -0.2, -0.1, 0.1, 0.2])
    curves = np.full((5, 4, len(lags)), np.nan)
    for index, (limit, exponent) in enumerate(
        ((100, 1.7), (1000, 1.76), (10000, 1.8)), 1
    ):
        take = lags <= limit
        curves[:, index, take] = lags[take] ** (exponent + shared_slope_noise[:, None])
        # A long-scale crossover must not contaminate the common short fit.
        curves[:, index, lags >= 1000] *= 2
    comparisons = MODULE["cohort_h_comparisons"](lags, curves)
    short = comparisons["10-100"]
    assert set(short["fits"]) == {"100", "1000", "10000"}
    np.testing.assert_allclose(
        [short["fits"][key]["hurst"]["point"] for key in ("100", "1000", "10000")],
        [0.85, 0.88, 0.9],
    )
    # Wide marginal intervals coexist with an exactly known paired contrast.
    assert short["fits"]["100"]["hurst"]["high"] > 0.9
    for key, difference in (
        ("100_minus_1000", -0.03),
        ("100_minus_10000", -0.05),
        ("1000_minus_10000", -0.02),
    ):
        np.testing.assert_allclose(list(short["contrasts"][key].values()), difference)
    assert set(comparisons["10-1000"]["fits"]) == {"1000", "10000"}


def test_general_fit_reports_actual_endpoint_and_missing_bootstrap_support():
    lags = np.array([10, 100, 1000, 10000, 28440, 40000])
    curves = np.tile(lags**1.6, (6, 1))
    curves[:, -1] *= 1000  # Outside the requested fitting interval.
    curves[-1, -2] = np.nan
    result = MODULE["available_population_fit"](
        lags, curves, np.array([1000, 800, 500, 100, 7, 1])
    )
    np.testing.assert_allclose(list(result["hurst"].values()), 0.8)
    assert result["interval_s"] == (10, 30000)
    assert result["evaluated_lag_bounds_s"] == [10, 28440]
    assert result["lag_count"] == 5
    assert result["minimum_group_support"] == 7
    assert result["valid_bootstrap_replicates"] == 4
