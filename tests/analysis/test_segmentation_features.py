from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.segmentation.config import SegmentationConfig, SplitFractions
from soaring.analysis.segmentation.features import (
    build_feature_frame,
    valid_feature_block_indexes,
    valid_feature_matrix,
)


@pytest.fixture
def config() -> SegmentationConfig:
    return SegmentationConfig(
        decision_step_s=10.0,
        feature_window_s=30.0,
        max_native_dt_s=10.0,
        min_horizontal_speed_mps=1.0,
        states=("transition", "search", "climb"),
        covariance_type="full",
        random_seed=7,
        n_restarts=1,
        n_iter=5,
        tol=1e-3,
        min_covar=1e-3,
        split=SplitFractions(train=0.7, validation=0.15, test=0.15),
        max_fit_flights=10,
        max_fit_observations=1000,
        max_sequence_observations=100,
        bootstrap_replicates=10,
    )


def _segment(
    *, cadence: float = 1.0, vertical_speed: float = 0.0, turn_rate: float = 0.0
) -> pd.DataFrame:
    t = np.arange(0.0, 101.0, cadence)
    speed = 10.0
    angle = turn_rate * t
    v_e, v_n = speed * np.cos(angle), speed * np.sin(angle)
    a_e, a_n = -speed * turn_rate * np.sin(angle), speed * turn_rate * np.cos(angle)
    return pd.DataFrame(
        {
            "source": "paraglider",
            "flight_id": "one",
            "segment_id": 0,
            "t": t,
            "E": np.cumsum(v_e) * cadence,
            "N": np.cumsum(v_n) * cadence,
            "z": vertical_speed * t,
            "v_E": v_e,
            "v_N": v_n,
            "v_z": vertical_speed,
            "a_E": a_e,
            "a_N": a_n,
            "z_reconstructed": False,
            "z_derivative_reconstructed": False,
            "edge": False,
        }
    )


def test_straight_features_use_a_physical_window(config: SegmentationConfig) -> None:
    points = build_feature_frame(_segment(vertical_speed=-1.5), config)

    valid = points.loc[~points["feature_edge"]]
    assert points["t"].tolist() == list(np.arange(0.0, 101.0, 10.0))
    assert valid["t"].tolist() == list(np.arange(20.0, 81.0, 10.0))
    np.testing.assert_allclose(valid["mean_v_z"], -1.5)
    np.testing.assert_allclose(valid["mean_v_h"], 10.0)
    np.testing.assert_allclose(valid["mean_abs_turn_rate"], 0.0)
    np.testing.assert_allclose(valid["turn_coherence"], 0.0)


def test_circle_keeps_turn_direction_coherence(config: SegmentationConfig) -> None:
    points = build_feature_frame(_segment(vertical_speed=2.0, turn_rate=0.2), config)
    valid = points.loc[~points["feature_edge"]]

    np.testing.assert_allclose(valid["mean_v_z"], 2.0, atol=1e-12)
    np.testing.assert_allclose(valid["mean_abs_turn_rate"], 0.2, atol=1e-12)
    np.testing.assert_allclose(valid["turn_coherence"], 1.0, atol=1e-12)


def test_reversing_search_turn_has_low_direction_coherence(
    config: SegmentationConfig,
) -> None:
    segment = _segment(turn_rate=0.2)
    t = segment["t"].to_numpy(dtype=float)
    rate = np.where(t < 50.0, 0.2, -0.2)
    angle = np.where(t < 50.0, 0.2 * t, 10.0 - 0.2 * (t - 50.0))
    segment["v_E"] = 10.0 * np.cos(angle)
    segment["v_N"] = 10.0 * np.sin(angle)
    segment["a_E"] = -10.0 * rate * np.sin(angle)
    segment["a_N"] = 10.0 * rate * np.cos(angle)
    points = build_feature_frame(segment, config)
    reversal = points.loc[points["t"] == 50.0].iloc[0]

    assert reversal["mean_abs_turn_rate"] == pytest.approx(0.2)
    assert reversal["turn_coherence"] < 0.1


def test_features_are_cadence_invariant_after_time_integration(
    config: SegmentationConfig,
) -> None:
    first = build_feature_frame(
        _segment(cadence=1.0, vertical_speed=1.0, turn_rate=0.1), config
    )
    second = build_feature_frame(
        _segment(cadence=5.0, vertical_speed=1.0, turn_rate=0.1), config
    )

    np.testing.assert_allclose(
        valid_feature_matrix(first), valid_feature_matrix(second)
    )


def test_slow_segments_are_not_upsampled(config: SegmentationConfig) -> None:
    assert build_feature_frame(_segment(cadence=20.0), config).empty


def test_features_never_take_values_from_another_segment(
    config: SegmentationConfig,
) -> None:
    descent = build_feature_frame(_segment(vertical_speed=-4.0), config)
    climb = _segment(vertical_speed=3.0)
    climb["segment_id"] = 1
    ascent = build_feature_frame(climb, config)

    assert valid_feature_matrix(descent)[0, 0] == -4.0
    assert valid_feature_matrix(ascent)[0, 0] == 3.0


def test_quality_flags_mask_windows_and_create_independent_blocks(
    config: SegmentationConfig,
) -> None:
    segment = _segment(vertical_speed=2.0)
    segment.loc[segment["t"] == 50.0, "z_reconstructed"] = True
    segment.loc[segment["t"] == 70.0, "edge"] = True
    points = build_feature_frame(segment, config)

    masked = points.loc[points["quality_masked"], "t"].tolist()
    assert masked == [40.0, 50.0, 60.0, 70.0, 80.0]
    assert points.loc[points["quality_masked"], "mean_v_z"].isna().all()
    assert [block.tolist() for block in valid_feature_block_indexes(points)] == [
        [2, 3],
    ]


def test_quality_mask_covers_fixes_supporting_interpolated_window_endpoints(
    config: SegmentationConfig,
) -> None:
    segment = _segment(cadence=10.0)
    segment.loc[segment["t"] == 0.0, "z_reconstructed"] = True
    points = build_feature_frame(segment, config)

    assert bool(points.loc[points["t"] == 20.0, "quality_masked"].iloc[0])


def test_derivative_support_excludes_reconstruction_outside_feature_window(config):
    segment = _segment()
    segment.loc[segment.t == 57.0, "z_reconstructed"] = True
    segment.loc[segment.t.between(55.0, 59.0), "z_derivative_reconstructed"] = True
    points = build_feature_frame(segment, config)
    # The feature at 40 s integrates [25, 55]. The imputed fix at 57 s lies
    # outside, but its SG contribution to the derivative at 55 s is still unsafe.
    assert bool(points.loc[points.t == 40.0, "quality_masked"].iloc[0])
    assert not bool(points.loc[points.t == 30.0, "quality_masked"].iloc[0])


def test_fresh_features_refuse_legacy_input_without_derivative_provenance(config):
    with pytest.raises(ValueError, match="z_derivative_reconstructed"):
        build_feature_frame(
            _segment().drop(columns="z_derivative_reconstructed"), config
        )
