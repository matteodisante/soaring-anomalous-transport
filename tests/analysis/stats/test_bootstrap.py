"""The error bar has to count independent things, and these tests are what say it does."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.stats.bootstrap import (
    cluster_bootstrap,
    cluster_labels,
    intraclass_correlation,
    sampling_covariance,
)


def _clustered(n_groups, per_group, icc, seed=0):
    rng = np.random.default_rng(seed)
    labels = np.repeat(np.arange(n_groups), per_group)
    between = np.repeat(rng.normal(0.0, np.sqrt(icc), n_groups), per_group)
    within = rng.normal(0.0, np.sqrt(1.0 - icc), n_groups * per_group)
    return between + within, labels


@pytest.mark.parametrize("icc", [0.0, 0.3, 0.6, 0.9])
def test_intraclass_correlation_recovers_a_known_value(icc):
    values, labels = _clustered(300, 8, icc, seed=int(100 * icc))
    assert intraclass_correlation(values, labels) == pytest.approx(icc, abs=0.06)


def test_clustering_widens_the_error_bar_when_it_should():
    """The whole point: flights inside a cluster are not separate measurements."""
    values, labels = _clustered(200, 8, 0.9, seed=1)
    curves = values[:, None]
    _, per_flight = cluster_bootstrap(
        curves, np.arange(len(values)), lambda c: c[0], n_resamples=300, seed=2
    )
    _, clustered = cluster_bootstrap(
        curves, labels, lambda c: c[0], n_resamples=300, seed=2
    )
    # sqrt(1 + (m-1) rho) = sqrt(1 + 7*0.9) = 2.7 in theory.
    assert clustered.std() / per_flight.std() > 1.8


def test_clustering_changes_nothing_when_there_is_no_clustering():
    values, labels = _clustered(200, 8, 0.0, seed=3)
    curves = values[:, None]
    _, per_flight = cluster_bootstrap(
        curves, np.arange(len(values)), lambda c: c[0], n_resamples=300, seed=4
    )
    _, clustered = cluster_bootstrap(curves, labels, lambda c: c[0], n_resamples=300, seed=4)
    assert clustered.std() / per_flight.std() == pytest.approx(1.0, abs=0.35)


def test_cluster_labels_gives_missing_keys_their_own_cluster():
    """A missing date is not a shared day, and pooling them would fake independence."""
    frame = pd.DataFrame(
        {
            "date": ["2020-05-01", "2020-05-01", None, None],
            "takeoff": ["A", "A", "A", "B"],
        }
    )
    labels = cluster_labels(frame, "day_site")
    assert labels[0] == labels[1]
    assert len({labels[2], labels[3], labels[0]}) == 3


def test_cluster_labels_rejects_a_level_it_lacks_the_columns_for():
    with pytest.raises(KeyError):
        cluster_labels(pd.DataFrame({"takeoff": ["A"]}), "day_site")


def test_sampling_covariance_is_a_property_of_the_noise_not_of_the_shape():
    """The number a breakpoint null needs: it must not know the curve is bent."""
    rng = np.random.default_rng(5)
    lags = np.geomspace(10.0, 1000.0, 30)
    bent = lags**1.5 * (1.0 + 0.4 * np.tanh(np.log10(lags) - 1.5))
    curves = bent[None, :] * np.exp(rng.normal(0.0, 0.1, size=(400, 30)))
    result = sampling_covariance(curves, np.arange(400), n_resamples=80, seed=6)
    # 0.1 in natural log over 400 flights is ~0.043/sqrt(400) dex per lag.
    assert np.nanmedian(result["sigma_dex"]) < 0.01
    assert result["n_clusters"] == 400
