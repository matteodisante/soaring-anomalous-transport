"""Small on-disk examples of structural corruption that a verifier must reject."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location(
    "verify_dataset", Path(__file__).resolve().parents[2] / "scripts/verify_dataset.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_tables(root, *, infinity=False, absent_segment=False, duplicate_meta=False):
    n = 8
    frame = pd.DataFrame(
        {
            "source": "paraglider",
            "flight_id": "a",
            "segment_id": 0,
            "t": np.arange(n, dtype=float),
            "E": 10 * np.arange(n, dtype=float),
            "N": 0.0,
            "z": 1000.0,
            "v_E": 10.0,
            "v_N": 0.0,
            "v_z": 0.0,
            "a_E": 0.0,
            "a_N": 0.0,
            "a_z": 0.0,
            "edge": False,
            "interpolated": False,
        }
    )
    if infinity:
        frame.loc[4, "a_z"] = np.inf
    frame.to_parquet(root / "fixes.parquet")
    rows = [{"flight_id": "a", "segment_id": 0, "n_fix": n, "kept": True}]
    if absent_segment:
        rows.append({"flight_id": "a", "segment_id": 1, "n_fix": 20, "kept": True})
    pd.DataFrame(rows).to_parquet(root / "segments.parquet")
    meta = pd.DataFrame(
        {"flight_id": ["a"] * (2 if duplicate_meta else 1), "drop_reason": None}
    )
    meta.to_parquet(root / "flights_meta.parquet")


def test_consistent_small_archive_passes(tmp_path):
    write_tables(tmp_path)
    failures, _ = MODULE.verify("paragliders", tmp_path, 45.0)
    assert failures == []


@pytest.mark.parametrize(
    "defect, expected",
    [
        ("infinity", "non-finite"),
        ("absent_segment", "row count"),
        ("duplicate_meta", "duplicate flight_id"),
    ],
)
def test_verifier_rejects_structural_corruption(tmp_path, defect, expected):
    write_tables(tmp_path, **{defect: True})
    failures, _ = MODULE.verify("paragliders", tmp_path, 45.0)
    assert any(expected in message for message in failures)


def test_processing_exceptions_cannot_pass_as_scientific_exclusions(tmp_path):
    from soaring.analysis.preproc.pipeline import DROP_ERROR

    write_tables(tmp_path)
    meta = pd.read_parquet(tmp_path / "flights_meta.parquet")
    meta = pd.concat(
        [
            meta,
            pd.DataFrame(
                [
                    {
                        "flight_id": "broken",
                        "drop_reason": DROP_ERROR,
                        "drop_stage": "error",
                        "error_detail": "regression",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    meta.to_parquet(tmp_path / "flights_meta.parquet")
    failures, _ = MODULE.verify("paragliders", tmp_path, 45.0)
    assert any("pipeline errors" in item and "broken" in item for item in failures)
