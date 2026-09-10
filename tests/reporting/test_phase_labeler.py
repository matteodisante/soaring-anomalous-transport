from __future__ import annotations

import importlib.util
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "label_flight_phases", _ROOT / "scripts" / "label_flight_phases.py"
)
labeler = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(labeler)


def test_labeler_autosaves_and_reinstalls_span_after_redraw(tmp_path) -> None:
    time = np.arange(0.0, 60.0, 10.0)
    candidates = pd.DataFrame(
        {
            "candidate_id": "para-tra-01",
            "t": time,
            "E": time,
            "N": 0.0,
            "z": 1000.0 + time,
            "mean_v_z": 1.0,
            "mean_v_h": 10.0,
            "mean_abs_turn_rate": 0.1,
            "turn_coherence": 0.8,
        }
    )
    windows = pd.DataFrame(
        {
            "candidate_id": ["para-tra-01"],
            "discipline": ["paragliders"],
            "source": ["paraglider"],
            "flight_id": ["one"],
            "segment_id": [0],
            "split": ["train"],
            "window_start": [0.0],
            "window_end": [60.0],
        }
    )
    output = tmp_path / "phase_annotations.csv"
    app = labeler.AnnotationApp(candidates, windows, output, "tester")
    first_selector = app.span

    app._select(10.0, 30.0)
    app._add("climb")
    second_selector = app.span
    app._select(30.0, 50.0)
    app._add("transition")

    saved = pd.read_csv(output)
    assert saved["state"].tolist() == ["climb", "transition"]
    assert saved[["t_start", "t_end"]].to_numpy().tolist() == [
        [10.0, 30.0],
        [30.0, 50.0],
    ]
    assert second_selector is not first_selector
    assert app.span is not second_selector

    import matplotlib.pyplot as plt

    plt.close(app.figure)
