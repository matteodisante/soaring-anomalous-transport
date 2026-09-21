"""Check the estimand, orthogonal decomposition and paired uncertainty propagation."""

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.observables.factorial_transport import (
    COMPONENTS,
    bootstrap_summary,
    cell_masks,
    contrasts,
    decompose,
    diagnostics,
)


def test_masks_partition_only_admitted_flights_without_reordering():
    frame = pd.DataFrame(
        {
            "wing_class": ["C ou 2", "D ou 2-3", "Biplace", "A ou 1", "A ou 1"],
            "task": ["open", "closed", "open", None, "open"],
            "altitude_band": ["Plains", "High mountains", "Plains", "Hills", None],
            "lon0": [6] * 5,
            "lat0": [45] * 5,
        },
        index=[9, 4, 2, 8, 1],
    )
    masks = cell_masks(frame)
    assert len(masks) == 16
    np.testing.assert_array_equal(np.sum(list(masks.values()), axis=0), [1, 1, 0, 0, 0])
    assert masks["alt0_open_beginners"].tolist() == [True, False, False, False, False]
    assert masks["alt3_closed_experts"].tolist() == [False, True, False, False, False]


def test_decomposition_reconstructs_every_draw_and_partitions_sums_of_squares():
    h = np.random.default_rng(42).normal(size=(17, 4, 2, 2))
    parts = decompose(h)
    np.testing.assert_allclose(
        sum(parts[k] for k in ["mean", *COMPONENTS]), h, atol=1e-14
    )
    for key, factors in COMPONENTS.items():
        for axis in factors:
            np.testing.assert_allclose(parts[key].mean(axis=axis + 1), 0, atol=1e-14)
    terms = [parts[k].reshape(17, 16) for k in COMPONENTS]
    for i, term in enumerate(terms):
        for other in terms[i + 1 :]:
            np.testing.assert_allclose(np.sum(term * other, axis=1), 0, atol=1e-14)
    d = diagnostics(h)
    np.testing.assert_allclose(sum(c["share"] for c in d["components"].values()), 1)


def test_exact_additive_grid_has_no_interactions_and_matches_independent_ols():
    altitude = np.array([-0.04, 0.03, 0.02, -0.01])[:, None, None]
    circuit = np.array([0.02, -0.02])[None, :, None]
    equipment = np.array([-0.01, 0.01])[None, None, :]
    h = 0.85 + altitude + circuit + equipment
    np.testing.assert_allclose(decompose(h)["residual"], 0, atol=1e-15)
    i, j, k = np.indices((4, 2, 2)).reshape(3, -1)
    design = np.column_stack([np.ones(16), i == 1, i == 2, i == 3, j, k])
    arbitrary = np.random.default_rng(3).normal(size=(4, 2, 2))
    fitted = design @ np.linalg.lstsq(design, arbitrary.ravel(), rcond=None)[0]
    np.testing.assert_allclose(
        decompose(arbitrary)["additive"].ravel(), fitted, atol=1e-14
    )


def test_pure_three_way_interaction_is_not_misattributed_to_a_main_effect():
    a = np.array([-3, -1, 1, 3])[:, None, None]
    c = np.array([1, -1])[None, :, None]
    e = np.array([-1, 1])[None, None, :]
    h = 0.8 + 0.01 * a * c * e
    parts = decompose(h)
    for name in list(COMPONENTS)[:-1]:
        np.testing.assert_allclose(parts[name], 0, atol=1e-15)
    np.testing.assert_allclose(parts["three_way"], h - 0.8, atol=1e-15)
    np.testing.assert_allclose(diagnostics(h)["r2_add"], 0, atol=1e-14)


def test_paired_contrast_cancels_shared_noise_and_endpoint_sign_is_explicit():
    rng = np.random.default_rng(12)
    h = np.full((1001, 4, 2, 2), 0.8)
    h[:, 0, 0, 0] += 0.10
    h[:, 0, 0, 1] += 0.12
    h[:, 3, 0, 0] += 0.03
    h[:, 3, 0, 1] += 0.02
    h[1:] += rng.normal(0, 0.02, size=(1000, 1, 1, 1))
    endpoint = contrasts(h)["endpoints"]
    np.testing.assert_allclose(
        endpoint, np.tile([0.07, 0.10, 0.03], (1001, 1)), atol=1e-15
    )
    assert bootstrap_summary(endpoint)["se"].max() < 1e-14


def test_simultaneous_calibration_covers_the_declared_joint_bootstrap_family():
    rng = np.random.default_rng(82)
    observed = np.array([0.02, -0.03, 0.08])
    samples = np.vstack([observed, observed + rng.normal(size=(2000, 3)) * [1, 2, 3]])
    result = bootstrap_summary(samples)
    inside = np.all(
        (samples[1:] >= result["sim_low"]) & (samples[1:] <= result["sim_high"]), axis=1
    )
    assert abs(inside.mean() - 0.9) < 0.001
    np.testing.assert_allclose(result["se"], samples[1:].std(axis=0, ddof=1))
    np.testing.assert_allclose(result["low"], np.percentile(samples[1:], 5, axis=0))
    assert result["family_size"] == 3


def test_constant_grid_has_undefined_variation_shares_and_exact_zero_residual():
    result = diagnostics(np.ones((4, 2, 2)))
    assert np.isnan(result["r2_add"])
    assert result["residual_rms"] == 0
    summary = bootstrap_summary(np.ones((10, 2)))
    np.testing.assert_array_equal(summary["sim_low"], [1, 1])


@pytest.mark.parametrize("h", [np.ones((4, 2)), np.full((4, 2, 2), np.nan)])
def test_decomposition_rejects_incomplete_cells(h):
    with pytest.raises(ValueError):
        decompose(h)
