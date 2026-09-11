"""The streamed diagnostic must retain the full-sample denominator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location(
    "preproc_report",
    Path(__file__).resolve().parents[2]
    / "scripts/reporting/ch2_dataset/generate_preproc_figure.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_histograms_count_out_of_view_values_but_not_nonfinite(tmp_path):
    from soaring.analysis.config import load_preproc_config

    frame = pd.DataFrame(
        {
            "quantity": np.array([0, 0, 0, 2, 2, 2, 2, 3, 3, 3], dtype=np.int8),
            "value": np.array(
                [10, 50, 200, 2, 12, 100, np.nan, -500, 1000, 7000], dtype=np.float32
            ),
        }
    )
    path = tmp_path / "sample.parquet"
    frame.to_parquet(path)
    out = MODULE._stream_fixlevel_histograms(
        path, "paragliders", load_preproc_config().fix
    )
    assert out["v_xy"]["n_finite"] == 3
    assert out["v_xy"]["n_outside"] == 2
    assert out["v_xy"]["counts"].sum() == 2
    assert out["v_z_local"]["n_finite"] == 3
    assert out["v_z_local"]["n_outside"] == 2
    assert out["v_z_local"]["counts"].sum() == 2
    assert out["altitude"]["n_outside"] == 2
