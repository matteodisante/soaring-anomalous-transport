from __future__ import annotations

import pandas as pd
import pytest

from soaring.analysis.segmentation.labels import (
    bootstrap_macro_f1,
    classification_metrics,
    labels_for_points,
    semantic_mapping,
    validate_annotations,
)


def _annotations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["paraglider", "paraglider", "paraglider"],
            "flight_id": ["one", "one", "one"],
            "segment_id": [0, 0, 0],
            "t_start": [0.0, 20.0, 40.0],
            "t_end": [20.0, 40.0, 60.0],
            "state": ["transition", "search", "climb"],
            "split": ["train", "train", "train"],
            "annotator": ["tester", "tester", "tester"],
        }
    )


def test_mapping_is_a_one_to_one_hungarian_assignment() -> None:
    raw = [2, 2, 0, 0, 1, 1]
    labels = ["transition", "transition", "search", "search", "climb", "climb"]

    assert semantic_mapping(raw, labels) == {0: "search", 1: "climb", 2: "transition"}


def test_interval_annotations_align_with_decision_times() -> None:
    points = pd.DataFrame(
        {
            "source": "paraglider",
            "flight_id": "one",
            "segment_id": 0,
            "t": [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0],
        }
    )
    labels = labels_for_points(points, _annotations(), split="train")

    assert labels.fillna("unlabelled").tolist() == [
        "transition",
        "transition",
        "search",
        "search",
        "climb",
        "climb",
        "unlabelled",
        "unlabelled",
    ]


def test_state_mapping_requires_all_three_train_phases() -> None:
    with pytest.raises(ValueError, match="every phase"):
        semantic_mapping([0, 1, 2], ["transition", "transition", "search"])


def test_state_mapping_requires_support_for_every_assigned_component() -> None:
    with pytest.raises(ValueError, match="support"):
        semantic_mapping(
            [0, 0, 0, 1, 2],
            ["transition", "search", "climb", "transition", "transition"],
        )


def test_nonfinite_annotation_bounds_are_refused() -> None:
    annotations = _annotations()
    annotations.loc[0, "t_start"] = float("nan")

    with pytest.raises(ValueError, match="finite"):
        validate_annotations(annotations)


def test_noninteger_segment_ids_are_refused() -> None:
    annotations = _annotations()
    annotations["segment_id"] = annotations["segment_id"].astype(float)
    annotations.loc[0, "segment_id"] = 0.5

    with pytest.raises(ValueError, match="integers"):
        validate_annotations(annotations)


def test_overlapping_annotations_are_refused() -> None:
    annotations = _annotations()
    annotations.loc[1, "t_start"] = 10.0

    with pytest.raises(ValueError, match="overlap"):
        validate_annotations(annotations)


def test_metrics_and_flight_cluster_bootstrap() -> None:
    truth = ["transition", "search", "climb", "transition", "search", "climb"]
    prediction = ["transition", "search", "climb", "search", "search", "climb"]
    flights = ["a", "a", "a", "b", "b", "b"]
    metrics = classification_metrics(truth, prediction, flights)
    interval = bootstrap_macro_f1(truth, prediction, flights, seed=4, replicates=25)

    assert metrics.n_flights == 2
    assert metrics.n_points == 6
    assert 0.0 < metrics.macro_f1 < 1.0
    assert 0.0 <= interval[0] <= interval[1] <= 1.0
