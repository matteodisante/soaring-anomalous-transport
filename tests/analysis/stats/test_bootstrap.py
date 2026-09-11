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


@pytest.mark.parametrize("workers", [1, 3])
def test_cluster_sums_match_explicit_resampled_flights(monkeypatch, workers):
    """Unequal groups and missing support must keep the original flight weights."""
    monkeypatch.setenv("SOARING_MAX_WORKERS", str(workers))
    curves = np.arange(48, dtype=float).reshape(8, 3, 2) + 1
    curves[0, 2] = np.nan
    curves[1:4, 1] = np.nan
    labels = np.array([4, 4, 4, 4, 9, 9, 15, 20])

    def statistic(mean):
        return mean[:, 0] / mean[:, 1]

    point, actual = cluster_bootstrap(
        curves, labels, statistic, n_resamples=31, seed=91
    )
    members = [np.flatnonzero(labels == label) for label in np.unique(labels)]
    rng = np.random.default_rng(91)
    expected = []
    for _ in range(31):
        picked = rng.integers(0, len(members), size=len(members))
        rows = np.concatenate([members[i] for i in picked])
        expected.append(statistic(np.nanmean(curves[rows], axis=0)))
    np.testing.assert_allclose(point, statistic(np.nanmean(curves, axis=0)))
    np.testing.assert_allclose(actual, expected, rtol=2e-14, equal_nan=True)


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
    _, clustered = cluster_bootstrap(
        curves, labels, lambda c: c[0], n_resamples=300, seed=4
    )
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


def test_the_lag_correlation_survives_one_much_noisier_lag():
    """Pooled without standardising, one loud lag drives the correlation to zero.

    The lags of a variation curve do not share a scale -- sigma runs over two orders of
    magnitude across the full grid, because coverage decays -- so a correlation taken on the
    raw deviations is a variance-weighted average dominated by whichever lag is loudest.
    That matters beyond the estimator: the breakpoint null is built from this number, a
    smaller correlation makes the surrogate whiter, and a whiter surrogate breaks less
    often, so the error flows straight into an understated false-positive rate.

    Here the answer is known: the curves are an exact AR(1) along the lag axis.
    """
    rng = np.random.default_rng(4)
    n_curves, n_lags, rho_true = 400, 22, 0.90
    z = rng.standard_normal((n_curves, n_lags))
    x = np.zeros_like(z)
    x[:, 0] = z[:, 0]
    for i in range(1, n_lags):
        x[:, i] = rho_true * x[:, i - 1] + np.sqrt(1 - rho_true**2) * z[:, i]

    # One lag forty times noisier than the rest, which is milder than the real grid.
    scale = np.where(np.arange(n_lags) == 18, 40.0, 1.0)
    curves = np.exp((x * scale) * 0.01)

    result = sampling_covariance(curves, np.arange(n_curves), n_resamples=80, seed=7)
    assert result["autocorrelation"] == pytest.approx(rho_true, abs=0.1)


def test_cluster_keys_preserve_tuples_and_treat_blank_keys_as_unknown():
    frame = pd.DataFrame(
        {"date": ["a|b", "a", "d", "d", "d"], "takeoff": ["c", "b|c", " ", "", "valid"]}
    )
    labels = cluster_labels(frame, "day_site")
    assert len(np.unique(labels)) == 5
    assert cluster_labels(frame.iloc[:0], "day_site").size == 0
