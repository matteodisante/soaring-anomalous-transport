"""Coverage denominators include slow segments and exclude acquisition gaps."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.segmentation.coverage import (
    archive_coverage_summary,
    native_coverage_summary,
)
from soaring.viewer.data import phases_on_cleaned_fixes


def test_native_counts_and_duration_explain_unclassified_geometry():
    fixes = pd.DataFrame({"segment_id": [0] * 31 + [1, 1], "t": [*range(31), 100, 120]})
    points = pd.DataFrame(
        {
            "segment_id": [0, 0, 0, 0],
            "t": [0, 10, 20, 30],
            "phase": ["unclassified", "climb", "unclassified", "unclassified"],
            "feature_edge": [True, False, False, True],
            "quality_masked": [False, False, True, False],
        }
    )
    result = phases_on_cleaned_fixes(fixes, points, decision_step_s=10)
    summary = native_coverage_summary(result)
    assert summary["n_cleaned_fixes"] == 33
    assert summary["fixes_by_reason"] == {
        "feature_edge": 11,
        "classified": 10,
        "quality_masked": 10,
        "no_eligible_decisions": 2,
    }
    assert (
        summary["cleaned_duration_s"] == 50
    )  # excludes the 70-second inter-segment gap
    assert summary["unclassified_duration_percent"] == 80


def test_archive_percentages_keep_slow_segments_in_time_denominator(
    tmp_path, monkeypatch
):
    from soaring.analysis.segmentation.model import HMMArtifact

    artifact = SimpleNamespace(
        config=SimpleNamespace(
            decision_step_s=10.0, sequence_prior=SimpleNamespace(weight=0.0)
        )
    )
    monkeypatch.setattr(HMMArtifact, "load", lambda _: artifact)
    coverage = pd.DataFrame(
        {
            "source": ["para", "para"],
            "flight_id": ["1", "1"],
            "segment_id": [0, 1],
            "t_start": [0.0, 100.0],
            "t_end": [32.0, 120.0],
            "n_native_fixes": [33, 2],
            "n_decision_points": [4, 0],
            "n_classifiable_points": [2, 0],
            "status": ["decoded", "skipped_native_cadence"],
        }
    )
    coverage.to_parquet(tmp_path / "phase_coverage.parquet")
    points = pd.DataFrame(
        {
            "source": ["para"] * 4,
            "flight_id": ["1"] * 4,
            "segment_id": [0] * 4,
            "t": [0.0, 10.0, 20.0, 30.0],
            "phase": ["unclassified", "climb", "climb", "unclassified"],
            "feature_edge": [True, False, False, False],
            "quality_masked": [False, False, False, True],
        }
    )
    points.to_parquet(tmp_path / "phase_points.parquet")
    result = archive_coverage_summary(tmp_path)
    assert result["unclassified_decision_percent"] == 50.0
    assert result["cleaned_duration_s"] == 52.0
    assert result["unclassified_duration_percent"] == pytest.approx(100 * 32 / 52)
    assert result["seconds_by_reason"]["feature_edge"] == 5.0
    assert result["seconds_by_reason"]["quality_masked"] == 7.0
    assert result["seconds_by_reason"]["skipped_native_cadence"] == 20.0
    assert np.isclose(sum(result["seconds_by_reason"].values()), 52.0)
