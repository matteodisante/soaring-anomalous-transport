from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "generate_segmentation_report",
    _ROOT
    / "scripts"
    / "reporting"
    / "ch4_flight_phases"
    / "generate_segmentation_report.py",
)
report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(report)


def test_generated_metric_table_uses_every_reported_metric(
    tmp_path, monkeypatch
) -> None:
    destination = tmp_path / "segmentation_table.tex"
    monkeypatch.setattr(report, "OUT_TABLE", destination)
    macros: dict[str, str] = {}
    for discipline_tag in ("Para", "Hang"):
        for split_tag in ("Val", "Test"):
            macros |= {
                f"StatSeg{discipline_tag}{split_tag}AccuracyPct": "75.0",
                f"StatSeg{discipline_tag}{split_tag}MacroFOnePct": "70.0",
                f"StatSeg{discipline_tag}{split_tag}MacroFOneLowPct": "65.0",
                f"StatSeg{discipline_tag}{split_tag}MacroFOneHighPct": "75.0",
            }
            for state_tag in ("Transition", "Search", "Climb"):
                for metric in ("PrecisionPct", "RecallPct", "FOnePct"):
                    macros[f"StatSeg{discipline_tag}{split_tag}{state_tag}{metric}"] = (
                        "70.0"
                    )

    report._write_metric_table(macros)
    table = destination.read_text(encoding="utf-8")

    assert "\\label{tab:segmentationmetrics}" in table
    assert "\\StatSegParaTestSearchRecallPct" in table
    assert "\\StatSegHangValClimbFOnePct" in table
