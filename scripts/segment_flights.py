#!/usr/bin/env python3
"""Fit, decode, and evaluate the continuous three-phase Gaussian HMM.

Examples::

    uv run python scripts/segment_flights.py train --discipline paragliders \
        --annotations /path/to/phase_annotations.csv
    uv run python scripts/segment_flights.py apply --discipline "hang gliders"
    uv run python scripts/segment_flights.py evaluate --discipline paragliders \
        --annotations /path/to/phase_annotations.csv --split test

The command writes only below the chosen archive's ``derived/segmentation/`` directory.
It never changes the preprocessed ``fixes.parquet`` input.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from soaring.analysis.segmentation import load_segmentation_config  # noqa: E402
from soaring.analysis.segmentation.labels import load_annotations  # noqa: E402
from soaring.analysis.segmentation.pipeline import (  # noqa: E402
    apply_discipline,
    evaluate_discipline,
    train_discipline,
    validate_annotation_splits,
    write_metrics,
)
from soaring.reporting import DISCIPLINES  # noqa: E402


def _paths(discipline: str) -> tuple[Path, Path, Path]:
    """Resolve input and discipline-local segmentation artifact paths."""
    derived = DISCIPLINES[discipline].derived_dir()
    if derived is None:
        raise FileNotFoundError(f"{discipline}: derived/fixes.parquet is not reachable")
    root = derived / "segmentation"
    return derived / "fixes.parquet", root / "model", root


def main(argv: list[str] | None = None) -> int:
    """Run one explicit phase-segmentation stage."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["train", "apply", "evaluate", "all"])
    parser.add_argument("--discipline", choices=list(DISCIPLINES), required=True)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--split", choices=["validation", "test"], default="validation")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)

    needs_annotations = args.action in {"train", "evaluate", "all"}
    if needs_annotations and args.annotations is None:
        parser.error("--annotations is required for training and evaluation")
    config = load_segmentation_config(args.config)
    fixes, model_dir, output_dir = _paths(args.discipline)
    annotations = load_annotations(str(args.annotations)) if args.annotations else None

    if args.action in {"train", "all"}:
        train_discipline(fixes, model_dir, config, annotations)
        print(f"{args.discipline}: wrote HMM model to {model_dir}")
    if args.action in {"apply", "all"}:
        points, runs = apply_discipline(fixes, model_dir, output_dir)
        print(f"{args.discipline}: wrote {points.name} and {runs.name}")
    if args.action in {"evaluate", "all"}:
        assert annotations is not None  # constrained by the argument parser above
        annotations = validate_annotation_splits(
            annotations, pd.read_parquet(model_dir / "split_manifest.parquet")
        )
    if args.action == "evaluate":
        metrics, interval = evaluate_discipline(
            output_dir / "phase_points.parquet",
            annotations,
            split=args.split,
            config=config,
        )
        output = output_dir / f"metrics_{args.split}.json"
        write_metrics(output, metrics, interval)
        print(
            f"{args.discipline}: {args.split} macro-F1={metrics.macro_f1:.3f} "
            f"({interval[0]:.3f}, {interval[1]:.3f}); wrote {output.name}"
        )
    if args.action == "all":
        for split in ("validation", "test"):
            metrics, interval = evaluate_discipline(
                output_dir / "phase_points.parquet",
                annotations,
                split=split,
                config=config,
            )
            output = output_dir / f"metrics_{split}.json"
            write_metrics(output, metrics, interval)
            print(
                f"{args.discipline}: wrote {output.name} "
                f"(macro-F1={metrics.macro_f1:.3f})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
