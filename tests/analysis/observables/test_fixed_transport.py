"""Sampling identities, discontinuities and coupled-bootstrap regression cases."""

import numpy as np

from soaring.analysis.observables.fixed_bootstrap import (
    bootstrap_means,
    cluster_draws,
    mixture_quantiles,
)
from soaring.analysis.observables.fixed_transport import (
    centred_excess,
    cohort_manifest,
    increments,
    launch_curve,
    log_fit,
    native_short_msd,
    selected_segments,
)


def test_fixed_segments_do_not_reenter_at_short_lags():
    row = {
        "flight_id": "a",
        "segments": [(0, 1401), (1401, 1702)],
        "segment_ids": [4, 9],
    }
    main = selected_segments(row, 10000)
    assert main == [(0, 1401)]
    assert selected_segments(row, 100) == row["segments"]
    pos = np.column_stack((np.arange(1702), np.zeros(1702))).astype(float)
    pos[1401:] += 100000
    x = increments(pos, main, 1)
    assert len(x) == 1400
    np.testing.assert_array_equal(x[:, 0], 1)
    assert len(increments(pos, main, 1000)) == 401
    assert cohort_manifest([row], 10000)["members"][0]["segments"][0]["segment_id"] == 4


def test_boundary_uses_grid_duration_not_fix_count():
    assert not selected_segments({"segments": [(0, 1250)]}, 10000)
    assert selected_segments({"segments": [(0, 1251)]}, 10000) == [(0, 1251)]


def test_native_short_lags_require_exact_resolution():
    t = np.arange(0, 41, 4)
    xy = np.column_stack((2 * t, np.zeros(len(t))))
    result = native_short_msd([(t, xy)])
    assert np.flatnonzero(np.isfinite(result)).tolist() == [3, 7]
    np.testing.assert_allclose(result[[3, 7]], [64, 256])


def test_launch_uses_parent_clock_and_does_not_bridge_gaps():
    t1 = np.arange(0, 21, 5)
    t2 = np.arange(40, 61, 5)
    segments = [(t, np.column_stack((2 * t, np.zeros(len(t))))) for t in (t1, t2)]
    result = launch_curve(segments, np.array([1, 10, 25, 35, 45]))
    np.testing.assert_allclose(
        result, [np.nan, 400, np.nan, np.nan, 8100], equal_nan=True
    )


def test_global_fit_and_radial_second_moment_identity():
    lags = np.geomspace(10, 10000, 33)
    fit = log_fit(lags, 7 * lags**1.6)
    np.testing.assert_allclose(fit["slope"], 1.6)
    rng = np.random.default_rng(1)
    xy = rng.normal(size=(300, 2))
    np.testing.assert_allclose(
        np.mean(np.linalg.norm(xy, axis=1) ** 2),
        np.mean(xy[:, 0] ** 2) + np.mean(xy[:, 1] ** 2),
    )


def test_signed_kurtosis_centres_the_mixture_not_each_flight():
    x = np.array([-5.0, -2.0, 0.0, 1.0, 8.0])
    raw = np.array([(x**q).mean() for q in range(1, 5)])
    expected = np.mean((x - x.mean()) ** 4) / np.mean((x - x.mean()) ** 2) ** 2 - 3
    np.testing.assert_allclose(centred_excess(raw), expected)
    np.testing.assert_allclose(
        centred_excess(np.array([((x + 100) ** q).mean() for q in range(1, 5)])),
        expected,
        rtol=1e-8,
    )


def test_exact_cluster_quantiles_against_explicit_replication():
    rng = np.random.default_rng(91)
    sizes = np.array([73, 2, 61, 91, 7, 117])
    labels = np.array([0, 0, 1, 2, 2, 2])
    draws = cluster_draws(labels, 30, 19)
    values = np.round(rng.exponential(size=sizes.sum()), 2)
    owners = np.repeat(np.arange(len(sizes)), sizes)
    probs = [0.25, 0.5, 0.75, 0.9]
    expected = []
    order = np.argsort(values)
    for counts in draws:
        weights = counts[labels[owners]] / sizes[owners]
        cdf = np.cumsum(weights[order])
        target = np.array(probs) * counts[labels].sum()
        expected.append(values[order[np.searchsorted(cdf, target - 1e-12)]])
    for bins in [1, 7, 64, 1024]:
        actual = mixture_quantiles(values, sizes, labels, draws, probs, bins=bins)
        np.testing.assert_array_equal(actual, expected)


def test_equal_flight_quantile_is_not_mean_of_flight_quantiles():
    # Long zero-valued flight receives the same total mass as the short one.
    values = np.r_[np.zeros(100), [10.0, 20.0]]
    result = mixture_quantiles(
        values, [100, 2], [0, 1], np.ones((1, 2)), [0.25, 0.5, 0.75, 0.9], bins=8
    )
    np.testing.assert_array_equal(result, [[0, 0, 10, 20]])


def test_cluster_means_keep_flight_weight_and_missing_support():
    values = np.array([[0.0, np.nan], [10.0, 20.0], [100.0, 200.0]])
    labels = np.array([0, 0, 1])
    draws = np.array([[1, 1], [2, 1], [0, 2]])
    np.testing.assert_allclose(
        bootstrap_means(values, labels, draws), [[110 / 3, 110], [24, 80], [100, 200]]
    )


def test_saved_scaling_matches_direct_weighted_ballistic_mixture(tmp_path):
    import importlib.util
    from pathlib import Path

    import pandas as pd

    from soaring.analysis.observables.fixed_transport import ORDERS, PROBABILITIES

    path = Path(__file__).resolve().parents[3] / (
        "scripts/reporting/ch3_global_transport/measure_ch3_fixed.py"
    )
    spec = importlib.util.spec_from_file_location("measure_ch3_fixed_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    velocities = np.array([[2, -1], [-4, 3], [1, 2]], dtype=float)
    frames, rows = [], []
    for f, (n, velocity) in enumerate(zip([1301, 1401, 1601], velocities, strict=True)):
        row = {"flight_id": str(f), "segments": [(0, n)], "segment_ids": [f]}
        xy = np.arange(n)[:, None] * 10 * velocity
        rows.append(row)
        frames.append((row, xy))
    cohort = cohort_manifest(rows, 10000)
    tab = pd.DataFrame({"cluster": [0, 0, 1]})
    draws = np.array([[1, 1], [2, 0], [0, 2], [1, 2]], dtype=np.uint16)
    for tau in (10, 10000):
        module.scaling_lag(frames, tab, draws, cohort, tau, tmp_path, bins=16)
        with np.load(tmp_path / f"lag-{tau}.npz") as measured:
            amplitude = (
                np.column_stack(
                    (np.abs(velocities), np.linalg.norm(velocities, axis=1))
                )
                * tau
            )
            expected = bootstrap_means(
                amplitude[:, :, None] ** ORDERS, tab.cluster, draws
            )
            np.testing.assert_allclose(measured["moments"], expected, rtol=1e-12)
            raw = bootstrap_means(
                (velocities * tau)[:, :, None] ** np.arange(1, 5), tab.cluster, draws
            )
            np.testing.assert_allclose(
                measured["kurtosis"], centred_excess(raw), atol=1e-12, equal_nan=True
            )
            for c in range(3):
                wanted = mixture_quantiles(
                    amplitude[:, c],
                    [1, 1, 1],
                    tab.cluster,
                    draws,
                    PROBABILITIES,
                    bins=16,
                )
                np.testing.assert_array_equal(measured["quantiles"][:, c], wanted)
            assert str(measured["cohort_sha256"]) == cohort["sha256"]
    assert not list(tmp_path.glob(".increments-*"))
