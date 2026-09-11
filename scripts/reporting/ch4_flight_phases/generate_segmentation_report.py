#!/usr/bin/env python3
"""Generate Chapter-4 HMM diagnostics, trajectory examples, and metric macros.

Run this only after ``segment_flights.py all`` has produced a model and decoded points
for both disciplines. It derives every visual diagnostic from stored artifacts rather
than from an interactive trajectory inspection.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
# Static output contract for the provenance checker; paths may be built dynamically.
GENERATED_OUTPUTS = (
    "segmentation_model_para.pdf",
    "segmentation_model_hang.pdf",
    "segmentation_example_para.pdf",
    "segmentation_example_hang.pdf",
    "segmentation_confusion_para.pdf",
    "segmentation_confusion_hang.pdf",
)

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from soaring.analysis.derived import stream_flights  # noqa: E402
from soaring.analysis.segmentation import load_segmentation_config  # noqa: E402
from soaring.analysis.segmentation.features import (  # noqa: E402
    FEATURE_COLUMNS,
    valid_feature_block_indexes,
)
from soaring.analysis.segmentation.figures import (  # noqa: E402
    plot_confusion_matrix,
    plot_model_diagnostics,
    plot_phase_trajectory,
)
from soaring.analysis.segmentation.labels import STATES, load_annotations  # noqa: E402
from soaring.analysis.segmentation.model import HMMArtifact  # noqa: E402
from soaring.analysis.segmentation.pipeline import (  # noqa: E402
    evaluate_discipline,
    labelled_phase_predictions,
    write_metrics,
)
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    partial_write_refusal,
    tex_int,
    unreachable_reason,
    write_macros,
)

OUT_TEX = ROOT / "thesis" / "generated" / "segmentation.tex"
OUT_TABLE = ROOT / "thesis" / "generated" / "segmentation_table.tex"
OUT_FIT_TABLE = ROOT / "thesis" / "generated" / "segmentation_fit_table.tex"


def _first_trajectory(points_path: Path, manifest_path: Path):
    """Read a classifiable held-out segment for a reproducible visual check."""
    manifest = pd.read_parquet(manifest_path)
    held_out = {
        (str(row.source), str(row.flight_id))
        for row in manifest.loc[manifest["split"] == "validation"].itertuples(
            index=False
        )
    }
    for flight in stream_flights(points_path):
        identity = (str(flight["source"].iloc[0]), str(flight["flight_id"].iloc[0]))
        if identity not in held_out:
            continue
        classified = flight.loc[flight["phase"] != "unclassified"]
        if classified.empty:
            continue
        first = classified.iloc[0]
        return flight.loc[flight["segment_id"] == first["segment_id"]]
    raise ValueError(f"{points_path} has no classifiable validation-segment phase rows")


def _percent(value: float) -> str:
    """Format a probability as a macro-safe percentage."""
    return f"{100.0 * value:.1f}"


def _diagnostic_summary(root: Path, artifact: HMMArtifact) -> dict[str, object]:
    """Summarize likelihood, occupancy and duration on all three flight splits."""
    manifest = pd.read_parquet(root / "model" / "split_manifest.parquet")
    split_by_flight = {
        (str(row.source), str(row.flight_id)): str(row.split)
        for row in manifest.itertuples(index=False)
    }
    counts = {
        split: dict.fromkeys(STATES, 0) for split in ("train", "validation", "test")
    }
    likelihood = {
        split: {"total": 0.0, "n": 0} for split in ("train", "validation", "test")
    }
    point_columns = [
        "source",
        "flight_id",
        "segment_id",
        "feature_edge",
        "quality_masked",
        "phase",
        *FEATURE_COLUMNS,
    ]
    for flight in stream_flights(root / "phase_points.parquet", point_columns):
        identity = (str(flight["source"].iloc[0]), str(flight["flight_id"].iloc[0]))
        split = split_by_flight.get(identity)
        if split is None:
            raise ValueError(f"decoded flight {identity} is absent from split manifest")
        for _, segment in flight.groupby("segment_id", sort=False):
            for indexes in valid_feature_block_indexes(segment):
                values = segment.iloc[indexes][FEATURE_COLUMNS].to_numpy(dtype=float)
                scaled = artifact.scaler.transform(values)
                implementation = getattr(artifact.model, "implementation", "log")
                artifact.model.implementation = "log"
                try:
                    likelihood[split]["total"] += float(artifact.model.score(scaled))
                finally:
                    artifact.model.implementation = implementation
                likelihood[split]["n"] += len(values)
                phases = segment.iloc[indexes]["phase"].to_numpy(dtype=str)
                for state in STATES:
                    counts[split][state] += int(np.sum(phases == state))

    durations = {
        split: {
            state: {
                "n_runs": 0,
                "n_uncensored": 0,
                "sum_uncensored_s": 0.0,
                "n_left_censored": 0,
                "n_right_censored": 0,
            }
            for state in STATES
        }
        for split in ("train", "validation", "test")
    }
    run_columns = [
        "source",
        "flight_id",
        "phase",
        "duration_s",
        "left_censored",
        "right_censored",
    ]
    for flight in stream_flights(root / "phase_segments.parquet", run_columns):
        identity = (str(flight["source"].iloc[0]), str(flight["flight_id"].iloc[0]))
        split = split_by_flight.get(identity)
        if split is None:
            raise ValueError(f"decoded flight {identity} is absent from split manifest")
        for row in flight.itertuples(index=False):
            state = str(row.phase)
            durations[split][state]["n_runs"] += 1
            durations[split][state]["n_left_censored"] += int(row.left_censored)
            durations[split][state]["n_right_censored"] += int(row.right_censored)
            if not row.left_censored and not row.right_censored:
                durations[split][state]["n_uncensored"] += 1
                durations[split][state]["sum_uncensored_s"] += float(row.duration_s)

    by_split: dict[str, object] = {}
    for split in ("train", "validation", "test"):
        n_observations = int(likelihood[split]["n"])
        total_count = sum(counts[split].values())
        by_split[split] = {
            "n_observations": n_observations,
            "log_likelihood_per_observation": (
                likelihood[split]["total"] / n_observations if n_observations else None
            ),
            "occupancy": {
                state: counts[split][state] / total_count if total_count else None
                for state in STATES
            },
            "duration_s": {
                state: {
                    "n_runs": durations[split][state]["n_runs"],
                    "n_uncensored": durations[split][state]["n_uncensored"],
                    "n_left_censored": durations[split][state]["n_left_censored"],
                    "n_right_censored": durations[split][state]["n_right_censored"],
                    "mean_uncensored": (
                        durations[split][state]["sum_uncensored_s"]
                        / durations[split][state]["n_uncensored"]
                        if durations[split][state]["n_uncensored"]
                        else None
                    ),
                }
                for state in STATES
            },
        }
    return {
        "fit": {
            "n_observations": artifact.n_fit_observations,
            "n_sequences": artifact.n_fit_sequences,
            "selected_restart": artifact.selected_restart,
            "log_likelihood_per_observation": (
                artifact.fit_log_likelihood / artifact.n_fit_observations
                if artifact.n_fit_observations
                else None
            ),
            "restart_log_likelihood_per_observation": [
                score / artifact.n_fit_observations
                if score is not None and artifact.n_fit_observations
                else None
                for score in artifact.restart_log_likelihoods
            ],
            "restart_converged": artifact.restart_converged,
        },
        "splits": by_split,
    }


def _write_metric_table(macros: dict[str, str]) -> None:
    """Write the aggregate and state-wise held-out metric tables for Chapter 4."""
    lines = [
        "% Generated by scripts/reporting/ch4_flight_phases/"
        "generate_segmentation_report.py -- do not edit.",
        r"\begin{table*}[tb]",
        r"\centering",
        r"\small",
        r"\caption{Flight-phase validation. Percentages are calculated at the "
        r"\SI{10}{\second} decision points; test macro-F1 intervals use a "
        r"flight-cluster bootstrap.}",
        r"\label{tab:segmentationmetrics}",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Discipline & Val. accuracy & Val. macro-F1 & Test accuracy & "
        r"Test macro-F1 & Test 95\% CI \\",
        r"\midrule",
    ]
    available = []
    for discipline in DISCIPLINES.values():
        tag = discipline.tag
        if f"StatSeg{tag}TestMacroFOnePct" not in macros:
            continue
        available.append(discipline)
        lines.append(
            f"{discipline.name.capitalize()} & "
            f"\\StatSeg{tag}ValAccuracyPct\\% & "
            f"\\StatSeg{tag}ValMacroFOnePct\\% & "
            f"\\StatSeg{tag}TestAccuracyPct\\% & "
            f"\\StatSeg{tag}TestMacroFOnePct\\% & "
            f"[\\StatSeg{tag}TestMacroFOneLowPct, "
            f"\\StatSeg{tag}TestMacroFOneHighPct]\\% \\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\par\medskip",
            r"\begin{tabular}{llrrrrrr}",
            r"\toprule",
            r"& & \multicolumn{3}{c}{Validation} & "
            r"\multicolumn{3}{c}{Test} \\",
            r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}",
            r"Discipline & Phase & Precision & Recall & F1 & "
            r"Precision & Recall & F1 \\",
            r"\midrule",
        ]
    )
    state_tags = {"transition": "Transition", "search": "Search", "climb": "Climb"}
    for discipline in available:
        for state in STATES:
            tag = discipline.tag
            state_tag = state_tags[state]
            lines.append(
                f"{discipline.name.capitalize()} & {state} & "
                f"\\StatSeg{tag}Val{state_tag}PrecisionPct\\% & "
                f"\\StatSeg{tag}Val{state_tag}RecallPct\\% & "
                f"\\StatSeg{tag}Val{state_tag}FOnePct\\% & "
                f"\\StatSeg{tag}Test{state_tag}PrecisionPct\\% & "
                f"\\StatSeg{tag}Test{state_tag}RecallPct\\% & "
                f"\\StatSeg{tag}Test{state_tag}FOnePct\\% \\\\"
            )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}"])
    OUT_TABLE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_fit_table() -> None:
    """Write the always-available archive-scale fitting and decoding census."""
    lines = [
        "% Generated by scripts/reporting/ch4_flight_phases/"
        "generate_segmentation_report.py -- do not edit.",
        r"\begin{table}[tb]",
        r"\centering",
        r"\small",
        r"\caption{Archive-scale HMM fit and decoding census.  A sequence is a "
        r"contiguous classifiable feature block; restart numbers are one-based.}",
        r"\label{tab:segmentationfit}",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Discipline & Fit flights & Fit sequences & Fit points & Decoded points & "
        r"Restart \\",
        r"\midrule",
    ]
    for discipline in DISCIPLINES.values():
        tag = discipline.tag
        lines.append(
            f"{discipline.name.capitalize()} & "
            f"\\StatSeg{tag}FitFlights & "
            f"\\StatSeg{tag}FitSequences & "
            f"\\StatSeg{tag}FitObservations & "
            f"\\StatSeg{tag}DecodedPoints & "
            f"\\StatSeg{tag}SelectedRestart/10 \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    OUT_FIT_TABLE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    discipline: str, annotations: pd.DataFrame | None, expected_config
) -> dict[str, str]:
    """Generate available thesis artifacts for one independently fitted discipline."""
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
    if expected_config is not None and artifact.config != expected_config:
        raise ValueError(f"{discipline}: reporting config differs from fitted HMM")
    generated = ROOT / "thesis" / "generated"
    plot_model_diagnostics(artifact, generated / f"segmentation_model_{slug}.pdf")
    plot_phase_trajectory(
        _first_trajectory(points_path, model_dir / "split_manifest.parquet"),
        generated / f"segmentation_example_{slug}.pdf",
    )
    import pyarrow.parquet as pq

    sample = pd.read_parquet(
        model_dir / "fit_sample_manifest.parquet", columns=["source", "flight_id"]
    )
    macros: dict[str, str] = {
        f"StatSeg{tag}FitObservations": tex_int(artifact.n_fit_observations),
        f"StatSeg{tag}FitSequences": tex_int(artifact.n_fit_sequences),
        f"StatSeg{tag}FitFlights": tex_int(
            len(sample.drop_duplicates(["source", "flight_id"]))
        ),
        f"StatSeg{tag}SelectedRestart": str(artifact.selected_restart + 1),
        f"StatSeg{tag}DecodedPoints": tex_int(
            pq.ParquetFile(points_path).metadata.num_rows
        ),
        f"StatSeg{tag}DecodedRuns": tex_int(
            pq.ParquetFile(root / "phase_segments.parquet").metadata.num_rows
        ),
        f"StatSeg{tag}DecodedSegments": tex_int(
            pq.ParquetFile(root / "phase_coverage.parquet").metadata.num_rows
        ),
    }
    if annotations is None:
        return macros
    for split, label in (("validation", "Val"), ("test", "Test")):
        metrics, interval = evaluate_discipline(
            points_path, annotations, split=split, config=artifact.config
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
        state_tags = {
            "transition": "Transition",
            "search": "Search",
            "climb": "Climb",
        }
        for state, values in metrics.per_state.items():
            state_tag = state_tags[state]
            macros |= {
                f"StatSeg{tag}{label}{state_tag}PrecisionPct": _percent(
                    values["precision"]
                ),
                f"StatSeg{tag}{label}{state_tag}RecallPct": _percent(values["recall"]),
                f"StatSeg{tag}{label}{state_tag}FOnePct": _percent(values["f1"]),
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
    diagnostics = _diagnostic_summary(root, artifact)
    (root / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return macros


def main(argv: list[str] | None = None) -> int:
    """Generate the two-discipline thesis reporting bundle."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--annotations",
        type=Path,
        help=(
            "validated interval labels; omit to generate provisional model and "
            "trajectory diagnostics without validation metrics"
        ),
    )
    parser.add_argument(
        "--examples-only",
        action="store_true",
        help="Redraw only the ten-minute held-out trajectory examples",
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args(argv)
    if args.examples_only:
        for discipline in DISCIPLINES.values():
            derived = discipline.derived_dir(
                require="segmentation/phase_points.parquet"
            )
            if derived is None:
                raise FileNotFoundError(f"{discipline.name}: phase archive unavailable")
            root = derived / "segmentation"
            points = _first_trajectory(
                root / "phase_points.parquet", root / "model/split_manifest.parquet"
            )
            output = (
                ROOT
                / "thesis/generated"
                / f"segmentation_example_{discipline.slug}.pdf"
            )
            plot_phase_trajectory(points, output)
            print(
                f"{discipline.name}: wrote {output.name} "
                f"(first 10 min, flight {points.flight_id.iloc[0]})"
            )
        return 0
    annotations = load_annotations(str(args.annotations)) if args.annotations else None
    config = load_segmentation_config(args.config) if args.config else None
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
    _write_fit_table()
    if annotations is not None:
        _write_metric_table(macros)
        products = f"{OUT_TEX.name}, {OUT_TABLE.name}, and validated figures"
    else:
        products = (
            f"{OUT_TEX.name}, {OUT_FIT_TABLE.name}, and provisional diagnostic figures"
        )
    print(f"wrote {products}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
