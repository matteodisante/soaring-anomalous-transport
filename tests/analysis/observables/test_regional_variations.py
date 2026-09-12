import numpy as np
import pandas as pd
import pytest

from soaring.analysis.observables.regional_variations import (
    REGIONS,
    bootstrap_moments,
    common_stratum_weights,
    flight_variations,
    measure_regional_variations,
    mixture_moments,
    moment_diagnostics,
    vector_moments,
)


def test_constant_velocity_invariance_and_constant_acceleration():
    t = np.arange(101, dtype=float)
    acceleration = np.array([0.3, -0.2])
    positions = 0.5 * t[:, None] ** 2 * acceleration
    row = {"segments": [(0, 101)]}
    stats, counts, _ = flight_variations(
        row, positions, [1, 2, 5], grid_s=1, common_max_s=5
    )
    drifted = positions + np.array([1300, -20]) + t[:, None] * [50, -30]
    shifted, _, _ = flight_variations(row, drifted, [1, 2, 5], grid_s=1, common_max_s=5)
    np.testing.assert_allclose(stats[:, :, 1:], shifted[:, :, 1:], atol=1e-9)
    value = moment_diagnostics(stats)["variation"]
    expected = np.sum(acceleration**2) * np.array([1, 2, 5]) ** 4
    np.testing.assert_allclose(
        value[:, :, 1], np.broadcast_to(expected, (3, 3)), atol=1e-9
    )
    np.testing.assert_allclose(value[:, :, 2], 0, atol=1e-18)
    np.testing.assert_array_equal(counts[1, :, 0], counts[1, :, 2])
    assert np.unique(counts[2]).size == 1


def test_segment_offsets_never_create_spurious_variation():
    first = np.column_stack([np.arange(20), np.zeros(20)])
    second = first + np.array([10000, -5000])
    row = {"segments": [(0, 20), (20, 40)]}
    stats, counts, _ = flight_variations(
        row, np.r_[first, second], [1, 5, 10], grid_s=1, common_max_s=5
    )
    values = moment_diagnostics(stats)["variation"]
    np.testing.assert_allclose(values[0, :2, 1:], 0)
    assert counts[0, 2, 0] == 2
    assert counts[0, 2, 1] == 0
    assert np.isnan(values[0, 2, 1])
    assert np.unique(counts[2, :2]).size == 1


def test_circle_exact_second_and_third_differences():
    t = np.arange(501)
    omega, radius = 0.05, 20
    positions = radius * np.column_stack([np.cos(omega * t), np.sin(omega * t)])
    lags = np.array([1, 3, 10])
    stats, _, _ = flight_variations({}, positions, lags, grid_s=1, common_max_s=10)
    values = moment_diagnostics(stats)["variation"]
    for order in (1, 2, 3):
        expected = radius**2 * (4 * np.sin(omega * lags / 2) ** 2) ** order
        np.testing.assert_allclose(
            values[:, :, order - 1], np.broadcast_to(expected, (3, 3)), rtol=1e-10
        )


def test_mixture_retains_between_flight_variability_and_rotation():
    rng = np.random.default_rng(13)
    groups = [rng.normal(size=(80, 2)), rng.normal(size=(20, 2)) + np.array([20, -5])]
    stats = np.array([vector_moments(x) for x in groups])
    pooled = mixture_moments(stats, [80, 20])
    np.testing.assert_allclose(pooled, vector_moments(np.concatenate(groups)))
    assert mixture_moments(stats)[0] != pytest.approx(pooled[0])
    angle = 0.37
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    )
    rotated = mixture_moments(
        np.array([vector_moments(x @ rotation.T) for x in groups])
    )
    original = moment_diagnostics(mixture_moments(stats))
    result = moment_diagnostics(rotated)
    assert result["variation"] == pytest.approx(original["variation"])
    assert result["anisotropy"] == pytest.approx(original["anisotropy"])
    assert (result["axis_deg"] - original["axis_deg"]) % 180 == pytest.approx(
        np.degrees(angle)
    )


def test_bootstrap_preserves_order_pairing_and_missing_support():
    stats = np.zeros((12, 2, 3, 5))
    stats[..., 2] = np.arange(1, 13)[:, None, None]
    stats[:, :, 1, 2] *= 2
    stats[:, :, 2, 2] *= 6
    stats[:4, 1] = np.nan
    point, replicates = bootstrap_moments(
        stats, np.repeat(np.arange(6), 2), n_resamples=30
    )
    np.testing.assert_allclose(point, mixture_moments(stats))
    values = moment_diagnostics(replicates)["variation"]
    np.testing.assert_allclose(values[:, :, 2] / values[:, :, 1], 3)
    _, repeat = bootstrap_moments(stats, np.repeat(np.arange(6), 2), n_resamples=30)
    np.testing.assert_array_equal(replicates, repeat)


def test_common_strata_exclude_unmatched_contexts_and_equalise_composition():
    rows = []
    for k, region in enumerate(REGIONS):
        for task, n in [("open", 2 + k), ("closed", 5 - k)]:
            rows.extend(
                [
                    {
                        "region": region,
                        "task_group": task,
                        "duration_band": "2-4h",
                        "period": "2020+",
                        "equipment_group": "AB",
                    }
                ]
                * n
            )
    rows.append(
        {
            "region": REGIONS[0],
            "task_group": "unknown",
            "duration_band": None,
            "period": "2020+",
            "equipment_group": "AB",
        }
    )
    metadata = pd.DataFrame(rows)
    weights, record = common_stratum_weights(
        metadata, np.ones(len(rows), dtype=bool), minimum_per_region=2
    )
    assert record["n_strata"] == 2
    assert weights[-1] == 0
    for region in REGIONS:
        mask = metadata.region.eq(region)
        assert weights[mask].sum() == pytest.approx(1)
        assert weights[mask & metadata.task_group.eq("open")].sum() == pytest.approx(
            2 / 5
        )


def test_parallel_measurement_preserves_every_flight_and_distribution(tmp_path):
    rng = np.random.default_rng(32)
    frames = [
        (
            {
                "flight_id": str(i),
                "region": REGIONS[i % 3],
                "segments": [(0, 90), (90, 150)],
            },
            np.cumsum(rng.normal(size=(150, 2)), axis=0),
        )
        for i in range(9)
    ]
    serial = measure_regional_variations(
        frames, tmp_path / "serial", lags_s=[10, 100], common_max_s=100
    )
    parallel = measure_regional_variations(
        frames, tmp_path / "parallel", lags_s=[10, 100], common_max_s=100, workers=2
    )
    assert serial[0] == parallel[0]
    np.testing.assert_array_equal(serial[1], parallel[1])
    np.testing.assert_array_equal(serial[2], parallel[2])
    assert serial[3] == parallel[3]
    for distribution in serial[3]:
        assert sum(distribution["probability"]) == pytest.approx(1)


def test_position_error_amplification_and_brownian_order_reference():
    rng = np.random.default_rng(813)
    errors = rng.normal(size=(150000, 2))
    for order, noise_gain in ((2, 6), (3, 20)):
        variation = np.mean(np.sum(np.diff(errors, n=order, axis=0) ** 2, axis=1))
        assert variation == pytest.approx(2 * noise_gain, rel=0.015)
    brownian = np.cumsum(errors, axis=0)
    v2 = np.mean(np.sum(np.diff(brownian, n=2, axis=0) ** 2, axis=1))
    v3 = np.mean(np.sum(np.diff(brownian, n=3, axis=0) ** 2, axis=1))
    assert v3 / v2 == pytest.approx(3, rel=0.01)
