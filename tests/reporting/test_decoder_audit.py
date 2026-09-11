from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.segmentation import load_segmentation_config
from soaring.analysis.segmentation.config import SequencePrior
from soaring.analysis.segmentation.model import HMMArtifact, Standardizer

_ROOT = Path(__file__).resolve().parents[2]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(
        name,
        _ROOT / "scripts/reporting/ch4_flight_phases" / f"{name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = _script("generate_decoder_audit")
pack = _script("prepare_annotation_pack")


def test_current_audit_keeps_fit_immutable_and_rejects_changed_features() -> None:
    current = load_segmentation_config()
    original = replace(
        current, sequence_prior=SequencePrior(), marginalize_turn_coherence=False
    )
    legacy = HMMArtifact(
        model=object(),
        scaler=Standardizer(np.zeros(4), np.ones(4)),
        state_mapping={0: "transition", 1: "search", 2: "climb"},
        config=original,
        fit_log_likelihood=0,
        selected_restart=0,
    )
    result = audit.current_artifact(legacy, current)
    assert result.config.marginalize_turn_coherence
    assert result.model is legacy.model
    assert legacy.config == original
    with pytest.raises(ValueError, match="feature/fitting"):
        audit.current_artifact(legacy, replace(current, feature_window_s=60))


def test_annotation_window_stays_on_offset_decision_grid() -> None:
    times = 3.5 + np.arange(400) * 10.0
    points = pd.DataFrame({"t": times, "feature_edge": False, "quality_masked": False})
    row = pd.Series({"candidate_id": "offset-clock", "split": "validation"})
    start, end, complete = pack._window(points, row)
    assert (start - times[0]) % 10 == 0
    assert (end - times[0]) % 10 == 0
    assert end - start == 1800
    assert not complete


def test_existing_test_pack_excludes_known_development_flights() -> None:
    windows = pd.read_csv(
        _ROOT / "annotations/phase_labeling/annotation_windows.csv",
        dtype={"flight_id": str},
    )
    for discipline, excluded in pack.DEVELOPMENT_TEST_EXCLUSIONS.items():
        chosen = windows.loc[
            (windows.discipline == discipline) & (windows["split"] == "test")
        ]
        assert set(chosen.flight_id).isdisjoint(excluded)
    candidates = pd.read_parquet(
        _ROOT / "annotations/phase_labeling/annotation_candidates.parquet"
    )
    assert not any(c == "phase" or c.startswith("p_") for c in candidates.columns)
    for row in windows.itertuples(index=False):
        times = candidates.loc[candidates.candidate_id == row.candidate_id, "t"]
        assert row.window_start == times.min()
        assert row.window_end == times.max() + 10


def test_reference_is_four_dimensional_even_after_current_archive_rebuild():
    config = load_segmentation_config()
    saved = HMMArtifact(
        model=object(),
        scaler=Standardizer(np.zeros(4), np.ones(4)),
        state_mapping={0: "transition", 1: "search", 2: "climb"},
        config=config,
        fit_log_likelihood=0,
        selected_restart=0,
    )
    reference = audit.reference_artifact(saved)
    assert reference.config.sequence_prior.weight == 0
    assert reference.config.marginalize_turn_coherence is False
    assert saved.config.marginalize_turn_coherence is True
    assert saved.config.sequence_prior.weight == 0.75
    assert audit.current_artifact(saved, config).config == config
