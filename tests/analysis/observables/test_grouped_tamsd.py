"""Cluster weighting, missing support and descriptive slopes of grouped TAMSDs."""

import numpy as np
import pytest

from soaring.analysis.observables.grouped_tamsd import (
    clustered_summary,
    decade_slopes,
    mean_and_support,
)


def test_cluster_resampling_preserves_flight_weights_and_paired_controls():
    # Twenty sites, each with two low-value flights and one high-value flight.
    values = np.tile([1.0, 3.0, 11.0], 20)[:, None, None] * np.array(
        [[[1.0, 4.0], [2.0, 8.0]]]
    )
    labels = np.repeat(np.arange(20), 3)
    result = clustered_summary(values, labels, resamples=40)
    expected = np.array([[5.0, 20.0], [10.0, 40.0]])
    np.testing.assert_allclose(result["mean_m2"], expected)
    np.testing.assert_allclose(
        result["pointwise_95_m2"], np.stack([expected, expected])
    )
    assert (result["n_flights"] == 60).all()
    assert (result["n_clusters"] == 20).all()


def test_missing_lags_and_small_cluster_counts_do_not_create_intervals():
    values = np.array([[[1.0, np.nan], [np.nan, np.nan]], [[9.0, 16.0], [9.0, 16.0]]])
    result = clustered_summary(values, ["same", "same"], resamples=30)
    np.testing.assert_allclose(result["mean_m2"], [[5.0, 16.0], [9.0, 16.0]])
    np.testing.assert_array_equal(result["n_flights"], [[2, 1], [1, 1]])
    assert np.isnan(result["pointwise_95_m2"]).all()
    empty = clustered_summary(np.empty((0, 2, 4)), [], resamples=20)
    assert np.isnan(empty["mean_m2"]).all()
    assert not empty["n_flights"].any()
    with pytest.raises(ValueError, match="aligned"):
        clustered_summary(values, ["one"], resamples=10)


def test_unequal_cluster_sizes_keep_equal_flight_point_estimate():
    values = np.array([1.0, 3.0, 11.0])[:, None, None]
    point, count = mean_and_support(values)
    np.testing.assert_allclose(point, [[5.0]])
    assert count.item() == 3
    result = clustered_summary(values, ["a", "a", "b"], resamples=50)
    np.testing.assert_allclose(result["mean_m2"], point)
    assert result["n_clusters"].item() == 2


def test_separate_decade_slopes_describe_the_given_curve():
    lags = np.geomspace(10, 10000, 61)
    records = decade_slopes(3 * lags**1.7, lags)
    np.testing.assert_allclose([r["slope"] for r in records], 1.7)
    assert records[0]["actual_lags_s"][0] == 10
