from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.segmentation.config import SegmentationConfig, SplitFractions
from soaring.analysis.segmentation.labels import validate_annotations
from soaring.analysis.segmentation.model import HMMArtifact, Standardizer
from soaring.analysis.segmentation.pipeline import (
    _fit_sequences,
    _phase_points,
    _phase_runs,
    apply_discipline,
    build_fit_sample_manifest,
    build_split_manifest,
    calibrate_discipline,
    collect_fit_sample,
    evaluate_discipline,
    segment_flight,
    split_for_flight,
    validate_annotation_splits,
)


class _DeterministicModel:
    """Small pickle-safe HMM stand-in for output-contract tests."""

    transmat_ = np.full((3, 3), 1 / 3)

    def predict(self, values: np.ndarray) -> np.ndarray:
        return np.arange(len(values)) % 3

    def predict_proba(self, values: np.ndarray) -> np.ndarray:
        output = np.full((len(values), 3), 0.05)
        output[np.arange(len(values)), self.predict(values)] = 0.9
        return output


def _config() -> SegmentationConfig:
    return SegmentationConfig(
        decision_step_s=10.0,
        feature_window_s=30.0,
        max_native_dt_s=10.0,
        min_horizontal_speed_mps=1.0,
        states=("transition", "search", "climb"),
        covariance_type="full",
        random_seed=9,
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


def _artifact() -> HMMArtifact:
    return HMMArtifact(
        model=_DeterministicModel(),
        scaler=Standardizer(mean=np.zeros(4), scale=np.ones(4)),
        state_mapping={0: "transition", 1: "search", 2: "climb"},
        config=_config(),
        fit_log_likelihood=0.0,
        selected_restart=0,
    )


def test_phase_points_keep_feature_edges_and_posteriors() -> None:
    frame = pd.DataFrame(
        {
            "source": "paraglider",
            "flight_id": "one",
            "segment_id": 0,
            "t": [0.0, 10.0, 20.0, 30.0],
            "E": [0.0, 1.0, 2.0, 3.0],
            "N": 0.0,
            "z": 0.0,
            "feature_edge": [True, False, False, True],
            "quality_masked": [False, False, False, False],
            "mean_v_z": [np.nan, 0.0, 0.0, np.nan],
            "mean_v_h": [np.nan, 1.0, 1.0, np.nan],
            "mean_abs_turn_rate": [np.nan, 0.0, 0.0, np.nan],
            "turn_coherence": [np.nan, 0.0, 0.0, np.nan],
        }
    )
    points = _phase_points(frame, _artifact())

    assert points["phase"].tolist() == [
        "unclassified",
        "transition",
        "search",
        "unclassified",
    ]
    assert points.loc[1, "p_transition"] == 0.9
    assert np.isnan(points.loc[0, "p_transition"])


def test_phase_runs_mark_observable_edges_as_censored() -> None:
    points = pd.DataFrame(
        {
            "source": "paraglider",
            "flight_id": "one",
            "segment_id": 0,
            "t": [0.0, 10.0, 20.0, 30.0],
            "phase": ["unclassified", "climb", "climb", "unclassified"],
            "p_climb": [np.nan, 0.8, 0.9, np.nan],
        }
    )
    runs = _phase_runs(points, _config())

    assert len(runs) == 1
    assert runs.loc[0, "duration_s"] == 20.0
    assert bool(runs.loc[0, "left_censored"])
    assert bool(runs.loc[0, "right_censored"])


def test_phase_runs_do_not_join_across_an_unclassified_gap() -> None:
    points = pd.DataFrame(
        {
            "source": "paraglider",
            "flight_id": "one",
            "segment_id": 0,
            "t": [0.0, 10.0, 20.0, 30.0, 40.0],
            "phase": ["climb", "climb", "unclassified", "climb", "climb"],
            "p_climb": [0.8, 0.9, np.nan, 0.8, 0.9],
        }
    )
    runs = _phase_runs(points, _config())

    assert len(runs) == 2
    assert runs["duration_s"].tolist() == [20.0, 20.0]
    assert runs["left_censored"].tolist() == [True, True]
    assert runs["right_censored"].tolist() == [True, True]


def test_manifest_assignment_is_stable_at_flight_level(tmp_path) -> None:
    rows = []
    for flight_id in ("one", "two"):
        for t in (0.0, 1.0):
            rows.append({"source": "paraglider", "flight_id": flight_id, "t": t})
    path = tmp_path / "fixes.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    config = _config()
    manifest = build_split_manifest(path, config)

    assert len(manifest) == 2
    assert manifest.loc[0, "split"] == split_for_flight("paraglider", "one", config)
    assert manifest["flight_id"].is_unique


def test_fit_sample_uses_complete_sequences_within_memory_cap(tmp_path) -> None:
    rows = []
    for flight_id in ("one", "two"):
        for t in np.arange(0.0, 101.0, 10.0):
            rows.append(
                {
                    "source": "paraglider",
                    "flight_id": flight_id,
                    "segment_id": 0,
                    "t": t,
                    "E": 10.0 * t,
                    "N": 0.0,
                    "z": t,
                    "v_E": 10.0,
                    "v_N": 0.0,
                    "v_z": 1.0,
                    "a_E": 0.0,
                    "a_N": 0.0,
                    "z_reconstructed": False,
                    "z_derivative_reconstructed": False,
                    "edge": False,
                }
            )
    fixes = tmp_path / "fixes.parquet"
    pd.DataFrame(rows).to_parquet(fixes, index=False)
    config = replace(_config(), max_fit_observations=8, max_sequence_observations=100)
    manifest = pd.DataFrame(
        {
            "source": ["paraglider", "paraglider"],
            "flight_id": ["one", "two"],
            "split": ["train", "train"],
            "priority": [1, 2],
        }
    )

    sample = build_fit_sample_manifest(fixes, manifest, config)
    sequences = _fit_sequences(fixes, sample, config)

    assert sample["n_observations"].sum() <= config.max_fit_observations
    assert sample["n_observations"].tolist() == [7]
    assert [len(sequence) for sequence in sequences] == [7]

    one_pass_sample, one_pass_sequences = collect_fit_sample(fixes, manifest, config)
    pd.testing.assert_frame_equal(one_pass_sample, sample)
    assert [len(sequence) for sequence in one_pass_sequences] == [7]


def test_split_manifest_uses_retained_flight_metadata_when_available(tmp_path) -> None:
    fixes = tmp_path / "fixes.parquet"
    pd.DataFrame(
        {"source": ["paraglider"], "flight_id": ["kept"], "t": [0.0]}
    ).to_parquet(fixes, index=False)
    pd.DataFrame(
        {
            "source": ["paraglider", "paraglider"],
            "flight_id": ["kept", "dropped"],
            "drop_stage": [pd.NA, "duration"],
            "n_segments_kept": [1.0, 0.0],
        }
    ).to_parquet(tmp_path / "flights_meta.parquet", index=False)

    manifest = build_split_manifest(fixes, _config())

    assert manifest["flight_id"].tolist() == ["kept"]


def test_manifest_validation_scopes_a_combined_annotation_file() -> None:
    manifest = pd.DataFrame(
        {
            "source": ["paraglider"],
            "flight_id": ["one"],
            "split": ["train"],
            "priority": [1],
        }
    )
    annotations = validate_annotations(
        pd.DataFrame(
            {
                "source": ["paraglider", "hangglider"],
                "flight_id": ["one", "other"],
                "segment_id": [0, 0],
                "t_start": [0.0, 0.0],
                "t_end": [10.0, 10.0],
                "state": ["transition", "climb"],
                "split": ["train", "test"],
                "annotator": ["tester", "tester"],
            }
        )
    )

    checked = validate_annotation_splits(annotations, manifest)

    assert checked["source"].tolist() == ["paraglider"]


def test_apply_and_evaluate_round_trip_with_parquet_artifacts(tmp_path) -> None:
    rows = []
    for t in np.arange(0.0, 101.0, 10.0):
        rows.append(
            {
                "source": "paraglider",
                "flight_id": "one",
                "segment_id": 0,
                "t": t,
                "E": 10.0 * t,
                "N": 0.0,
                "z": t,
                "v_E": 10.0,
                "v_N": 0.0,
                "v_z": 1.0,
                "a_E": 0.0,
                "a_N": 0.0,
                "z_reconstructed": False,
                "z_derivative_reconstructed": False,
                "edge": False,
            }
        )
    fixes = tmp_path / "fixes.parquet"
    pd.DataFrame(rows).to_parquet(fixes, index=False)
    root = tmp_path / "segmentation"
    model_dir = root / "model"
    artifact = _artifact()
    artifact.save(model_dir)
    pd.DataFrame(
        {
            "source": ["paraglider"],
            "flight_id": ["one"],
            "split": ["test"],
            "priority": [1],
        }
    ).to_parquet(model_dir / "split_manifest.parquet", index=False)

    points_path, runs_path = apply_discipline(fixes, model_dir, root)
    points = pd.read_parquet(points_path)
    interactive = segment_flight(pd.read_parquet(fixes), artifact)
    annotations = pd.DataFrame(
        {
            "source": "paraglider",
            "flight_id": "one",
            "segment_id": 0,
            "t_start": points["t"],
            "t_end": points["t"] + 10.0,
            "state": points["phase"].replace("unclassified", "transition"),
            "split": "test",
            "annotator": "tester",
        }
    )
    metrics, _ = evaluate_discipline(
        points_path, annotations, split="test", config=_config()
    )

    assert runs_path.is_file()
    pd.testing.assert_frame_equal(interactive, points, check_dtype=False)
    assert {"quality_masked", "p_transition", "p_search", "p_climb"}.issubset(
        points.columns
    )
    assert metrics.accuracy == 1.0


@pytest.mark.parametrize("prior_weight", [0.0, 0.75])
def test_calibrate_remaps_existing_points_and_posteriors_without_refitting(
    tmp_path,
    prior_weight,
    monkeypatch,
) -> None:
    rows = []
    for t in np.arange(0.0, 101.0, 10.0):
        rows.append(
            {
                "source": "paraglider",
                "flight_id": "one",
                "segment_id": 0,
                "t": t,
                "E": 10.0 * t,
                "N": 0.0,
                "z": t,
                "v_E": 10.0,
                "v_N": 0.0,
                "v_z": 1.0,
                "a_E": 0.0,
                "a_N": 0.0,
                "z_reconstructed": False,
                "z_derivative_reconstructed": False,
                "edge": False,
            }
        )
    fixes = tmp_path / "fixes.parquet"
    pd.DataFrame(rows).to_parquet(fixes, index=False)
    root = tmp_path / "segmentation"
    model_dir = root / "model"
    artifact = _artifact()
    from soaring.analysis.segmentation.config import SequencePrior

    artifact.mapping_method = "provisional-emission-signatures"
    artifact.config = replace(
        artifact.config, sequence_prior=SequencePrior(weight=prior_weight)
    )
    artifact.save(model_dir)
    pd.DataFrame(
        {
            "source": ["paraglider"],
            "flight_id": ["one"],
            "split": ["train"],
            "priority": [1],
        }
    ).to_parquet(model_dir / "split_manifest.parquet", index=False)
    points_path, _ = apply_discipline(fixes, model_dir, root)
    before = pd.read_parquet(points_path)
    usable = before.loc[before["phase_raw"].notna()].copy()
    manual_names = {0: "climb", 1: "transition", 2: "search"}
    annotations = pd.DataFrame(
        {
            "source": usable["source"],
            "flight_id": usable["flight_id"],
            "segment_id": usable["segment_id"],
            "t_start": usable["t"],
            "t_end": usable["t"] + 10.0,
            "state": usable["phase_raw"].astype(int).map(manual_names),
            "split": "train",
            "annotator": "tester",
        }
    )

    from soaring.analysis.segmentation import pipeline as pipeline_module

    calls = []
    original_decode = pipeline_module._phase_points

    def record_decode(frame, fitted):
        calls.append(fitted.state_mapping.copy())
        return original_decode(frame, fitted)

    monkeypatch.setattr(pipeline_module, "_phase_points", record_decode)
    calibrated = calibrate_discipline(root, annotations)
    assert bool(calls) == bool(prior_weight)
    assert all(mapping == manual_names for mapping in calls)
    after = pd.read_parquet(points_path)

    assert calibrated.mapping_method == "manual-train-hungarian"
    assert calibrated.state_mapping == manual_names
    classified = after["phase_raw"].notna()
    assert after.loc[classified, "phase"].tolist() == [
        manual_names[int(component)] for component in after.loc[classified, "phase_raw"]
    ]
    np.testing.assert_allclose(
        after.loc[classified, "p_climb"],
        before.loc[classified, "p_transition"],
    )


def test_apply_records_slow_segments_without_upsampling(tmp_path) -> None:
    fixes = tmp_path / "fixes.parquet"
    pd.DataFrame(
        {
            "source": "paraglider",
            "flight_id": "slow",
            "segment_id": 0,
            "t": [0.0, 20.0, 40.0],
            "E": [0.0, 200.0, 400.0],
            "N": 0.0,
            "z": 0.0,
            "v_E": 10.0,
            "v_N": 0.0,
            "v_z": 0.0,
            "a_E": 0.0,
            "a_N": 0.0,
            "z_reconstructed": False,
            "z_derivative_reconstructed": False,
            "edge": False,
        }
    ).to_parquet(fixes, index=False)
    root = tmp_path / "segmentation"
    model_dir = root / "model"
    _artifact().save(model_dir)

    points_path, runs_path = apply_discipline(fixes, model_dir, root)
    coverage = pd.read_parquet(root / "phase_coverage.parquet")

    assert pd.read_parquet(points_path).empty
    assert pd.read_parquet(runs_path).empty
    assert coverage["status"].tolist() == ["skipped_native_cadence"]
