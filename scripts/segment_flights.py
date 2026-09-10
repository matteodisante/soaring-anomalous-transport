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
import json
import shutil
import sys
from dataclasses import replace
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
    calibrate_discipline,
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
    parser.add_argument(
        "action", choices=["train", "apply", "calibrate", "evaluate", "all", "coverage"]
    )
    parser.add_argument("--discipline", choices=list(DISCIPLINES), required=True)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--split", choices=["validation", "test"], default="validation")
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--sequence-prior",
        "--current-decoder",
        action="store_true",
        help=(
            "Use configured sequence and emission decoding policies "
            "in a separate export"
        ),
    )
    args = parser.parse_args(argv)

    if args.sequence_prior and args.action not in {
        "apply",
        "coverage",
        "calibrate",
        "evaluate",
    }:
        parser.error(
            "--sequence-prior supports apply, coverage, calibrate and evaluate"
        )
    needs_annotations = args.action in {"calibrate", "evaluate", "all"}
    if needs_annotations and args.annotations is None:
        parser.error("--annotations is required for calibration and evaluation")
    config = load_segmentation_config(args.config)
    fixes, model_dir, output_dir = _paths(args.discipline)
    if args.sequence_prior:
        output_dir = output_dir / "sequence-prior"
        original_model = model_dir
        model_dir = output_dir / "model"
        if args.action == "apply":
            from soaring.analysis.segmentation.model import HMMArtifact

            artifact = HMMArtifact.load(original_model)
            artifact = replace(
                artifact,
                config=replace(
                    artifact.config,
                    sequence_prior=config.sequence_prior,
                    marginalize_turn_coherence=config.marginalize_turn_coherence,
                ),
            )
            artifact.save(model_dir)
            for manifest in original_model.glob("*manifest.parquet"):
                shutil.copy2(manifest, model_dir / manifest.name)
    if args.action == "coverage":
        from soaring.analysis.segmentation.coverage import archive_coverage_summary

        summary = archive_coverage_summary(output_dir)
        text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
        (output_dir / "coverage_summary.json").write_text(text, encoding="utf-8")
        print(text)
        return 0
    annotations = load_annotations(str(args.annotations)) if args.annotations else None

    if args.action in {"train", "all"}:
        train_discipline(fixes, model_dir, config, annotations)
        calibration = "manual" if annotations is not None else "provisional"
        print(f"{args.discipline}: wrote {calibration} HMM model to {model_dir}")
    if args.action in {"apply", "all"}:
        points, runs = apply_discipline(fixes, model_dir, output_dir)
        print(f"{args.discipline}: wrote {points.name} and {runs.name}")
    if args.action == "calibrate":
        assert annotations is not None
        artifact = calibrate_discipline(output_dir, annotations)
        print(
            f"{args.discipline}: calibrated state mapping "
            f"{artifact.state_mapping} from train annotations"
        )
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
