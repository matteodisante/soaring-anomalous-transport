#!/usr/bin/env python3
"""Generate Chapter-4 HMM diagnostics, trajectory examples, and metric macros.

Run this only after ``segment_flights.py all`` has produced a model and decoded points
for both disciplines. It derives every visual diagnostic from stored artifacts rather
than from an interactive trajectory inspection.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from soaring.analysis.segmentation import load_segmentation_config  # noqa: E402
from soaring.analysis.segmentation.figures import (  # noqa: E402
    plot_confusion_matrix,
    plot_model_diagnostics,
    plot_phase_trajectory,
)
from soaring.analysis.segmentation.labels import load_annotations  # noqa: E402
from soaring.analysis.segmentation.model import HMMArtifact  # noqa: E402
from soaring.analysis.segmentation.pipeline import (  # noqa: E402
    evaluate_discipline,
    labelled_phase_predictions,
    write_metrics,
)
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    partial_write_refusal,
    unreachable_reason,
    write_macros,
)

OUT_TEX = ROOT / "thesis" / "generated" / "segmentation.tex"


def _first_trajectory(points_path: Path):
    """Read one stored phase row group for a compact reproducible visual check."""
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(points_path)
    if parquet.metadata.num_row_groups == 0:
        raise ValueError(f"{points_path} has no phase rows")
    return parquet.read_row_group(0).to_pandas()


def _percent(value: float) -> str:
    """Format a probability as a macro-safe percentage."""
    return f"{100.0 * value:.1f}"


def run(discipline: str, annotations, config) -> dict[str, str]:
    """Generate every thesis artifact for one independently fitted discipline."""
    derived = DISCIPLINES[discipline].derived_dir()
    if derived is None:
        return {}
    root = derived / "segmentation"
    model_dir = root / "model"
    points_path = root / "phase_points.parquet"
    if not (model_dir / "metadata.json").is_file() or not points_path.is_file():
        return {}
    tag, slug = DISCIPLINES[discipline].tag, DISCIPLINES[discipline].slug
    artifact = HMMArtifact.load(model_dir)
    generated = ROOT / "thesis" / "generated"
    plot_model_diagnostics(artifact, generated / f"segmentation_model_{slug}.pdf")
    plot_phase_trajectory(
        _first_trajectory(points_path), generated / f"segmentation_example_{slug}.pdf"
    )
    macros: dict[str, str] = {}
    for split, label in (("validation", "Val"), ("test", "Test")):
        metrics, interval = evaluate_discipline(
            points_path, annotations, split=split, config=config
        )
        write_metrics(root / f"metrics_{split}.json", metrics, interval)
        macros |= {
            f"StatSeg{tag}{label}AccuracyPct": _percent(metrics.accuracy),
            f"StatSeg{tag}{label}MacroFOnePct": _percent(metrics.macro_f1),
            f"StatSeg{tag}{label}MacroFOneLowPct": _percent(interval[0]),
            f"StatSeg{tag}{label}MacroFOneHighPct": _percent(interval[1]),
            f"StatSeg{tag}{label}Points": str(metrics.n_points),
            f"StatSeg{tag}{label}Flights": str(metrics.n_flights),
        }
    truth, prediction, _ = labelled_phase_predictions(
        points_path, annotations, split="test"
    )
    plot_confusion_matrix(
        truth,
        prediction,
        generated / f"segmentation_confusion_{slug}.pdf",
        title=f"{discipline}: held-out test",
    )
    return macros


def main(argv: list[str] | None = None) -> int:
    """Generate the two-discipline thesis reporting bundle."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args(argv)
    annotations = load_annotations(str(args.annotations))
    config = load_segmentation_config(args.config)
    macros: dict[str, str] = {}
    missing: list[str] = []
    for discipline in DISCIPLINES:
        result = run(discipline, annotations, config)
        if result:
            macros |= result
        else:
            missing.append(discipline)
    refusal = partial_write_refusal(
        missing,
        OUT_TEX.name,
        allow_partial=args.allow_partial,
        reasons=[
            reason
            for name in missing
            if (reason := unreachable_reason(DISCIPLINES[name])) is not None
        ],
    )
    if refusal:
        print(refusal)
        return 1
    write_macros(
        OUT_TEX,
        macros,
        generator="scripts/reporting/ch4_flight_phases/generate_segmentation_report.py",
        sort=True,
    )
    print(f"wrote {OUT_TEX.name} and phase diagnostic figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
