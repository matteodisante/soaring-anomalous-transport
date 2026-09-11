#!/usr/bin/env python3
"""Regenerate Chapter 4 from the current decoder without rewriting archive labels.

Examples are full validation sequences re-decoded from their stored features before
cropping. The audit explicitly separates the original 4D fit/archive from the
configured 3D marginal and transition policy. No manual accuracy is estimated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, replace
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
# Static output contract for the provenance checker; paths may be built dynamically.
GENERATED_OUTPUTS = (
    "segmentation_current_example_para.pdf",
    "segmentation_current_example_hang.pdf",
    "segmentation_current_model_para.pdf",
    "segmentation_current_model_hang.pdf",
    "segmentation_decoder_ablation.pdf",
    "segmentation_decoding_transitions.pdf",
    "segmentation_coverage.pdf",
    "segmentation_decoder_audit.json",
    "segmentation_audit_table.tex",
    "segmentation_audit_values.tex",
)

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from soaring.analysis.segmentation import load_segmentation_config  # noqa: E402
from soaring.analysis.segmentation.config import SequencePrior  # noqa: E402
from soaring.analysis.segmentation.features import FEATURE_COLUMNS  # noqa: E402
from soaring.analysis.segmentation.figures import (  # noqa: E402
    plot_model_diagnostics,
    plot_phase_trajectory,
)
from soaring.analysis.segmentation.labels import STATES  # noqa: E402
from soaring.analysis.segmentation.model import (  # noqa: E402
    HMMArtifact,
    effective_transition_matrix,
)
from soaring.analysis.segmentation.pipeline import _phase_points  # noqa: E402
from soaring.reporting import DISCIPLINES, tex_int  # noqa: E402
from soaring.reporting.style import (
    PHASE_COLORS,
    STACK_GREYS,
    TRACE_COLOR,
    paper_style,
)

PALETTE = PHASE_COLORS

# The chapter's figures share the house style with the measured ones.
paper_style()


def current_artifact(legacy: HMMArtifact, config) -> HMMArtifact:
    """Apply only decoder choices; reject incompatible feature/fitting changes."""
    inherited = replace(
        config,
        sequence_prior=legacy.config.sequence_prior,
        marginalize_turn_coherence=legacy.config.marginalize_turn_coherence,
    )
    if inherited != legacy.config:
        raise ValueError("Current feature/fitting configuration differs from archive")
    return replace(legacy, config=config)


def reference_artifact(saved: HMMArtifact) -> HMMArtifact:
    """Reconstruct the fitted 4D reference, whatever the archived decoder."""
    return replace(
        saved,
        config=replace(
            saved.config,
            sequence_prior=SequencePrior(),
            marginalize_turn_coherence=False,
        ),
    )


def _validation_example(root: Path) -> pd.DataFrame:
    """Choose by fixed manifest priority, never by appealing predicted phases."""
    manifest = pd.read_parquet(root / "model/split_manifest.parquet")
    ordered = manifest.loc[manifest["split"] == "validation"].sort_values("priority")
    for row in ordered.itertuples(index=False):
        points = pd.read_parquet(
            root / "phase_points.parquet",
            filters=[
                ("source", "==", str(row.source)),
                ("flight_id", "==", str(row.flight_id)),
            ],
        )
        for _, segment in points.groupby("segment_id", sort=True):
            if (segment["phase"] != "unclassified").any():
                return segment.sort_values("t", kind="stable").reset_index(drop=True)
    raise ValueError(f"No classifiable validation segment in {root}")


def _ordered_matrix(artifact: HMMArtifact, *, fitted: bool) -> np.ndarray:
    inverse = {state: component for component, state in artifact.state_mapping.items()}
    indexes = [inverse[state] for state in STATES]
    matrix = (
        artifact.model.transmat_ if fitted else effective_transition_matrix(artifact)
    )
    return matrix[np.ix_(indexes, indexes)]


def _transition_figure(artifacts: dict[str, HMMArtifact], output: Path) -> None:
    import matplotlib.pyplot as plt

    with plt.rc_context({"pdf.fonttype": 42}):
        figure, axes = plt.subplots(2, 2, figsize=(6.1, 5.1), constrained_layout=True)
        for row, (discipline, artifact) in enumerate(artifacts.items()):
            for col, fitted in enumerate((True, False)):
                axis = axes[row, col]
                matrix = _ordered_matrix(artifact, fitted=fitted)
                axis.imshow(matrix, vmin=0, vmax=1, cmap="Blues")
                for i in range(3):
                    for j in range(3):
                        axis.text(
                            j,
                            i,
                            f"{matrix[i, j]:.3f}",
                            ha="center",
                            va="center",
                            color="white" if matrix[i, j] > 0.65 else "black",
                            fontsize=8.5,
                        )
                axis.set(
                    xticks=range(3),
                    yticks=range(3),
                    xticklabels=["T", "S", "C"],
                    yticklabels=["T", "S", "C"],
                    xlabel="Next phase (10 s later)",
                    ylabel="Current phase",
                )
                title = "Fitted matrix" if fitted else "Current decoding matrix"
                axis.set_title(f"{discipline.capitalize()}: {title.lower()}")
        figure.savefig(output, metadata={"CreationDate": None})
        plt.close(figure)


def _coverage_figure(summaries: dict[str, dict], output: Path) -> None:
    import matplotlib.pyplot as plt

    # Four parts of one excluded total, so a ramp rather than four hues: the bar
    # is a decomposition, and the rows beside it are already the two disciplines.
    categories = [
        ("quality_masked", "Reconstructed altitude / derivative edge", STACK_GREYS[0]),
        ("skipped_native_cadence", "Native cadence > 10 s", STACK_GREYS[1]),
        ("feature_edge", "Incomplete feature window", STACK_GREYS[2]),
        ("outside_decision_cells", "Tail outside decision cells", STACK_GREYS[3]),
    ]
    with plt.rc_context({"pdf.fonttype": 42}):
        figure, axis = plt.subplots(figsize=(6.1, 2.6))
        figure.subplots_adjust(left=0.2, right=0.97, top=0.92, bottom=0.40)
        left = np.zeros(len(summaries))
        for key, label, color in categories:
            values = np.array(
                [
                    100 * s["seconds_by_reason"][key] / s["cleaned_duration_s"]
                    for s in summaries.values()
                ]
            )
            axis.barh(
                range(len(values)),
                values,
                left=left,
                height=0.47,
                label=label,
                color=color,
            )
            left += values
        for row, value in enumerate(left):
            axis.text(value + 0.12, row, f"{value:.2f}%", va="center")
        axis.set(
            yticks=range(len(summaries)),
            yticklabels=[s.capitalize() for s in summaries],
            xlabel="Unclassified time / all retained cleaned duration [%]",
            xlim=(0, max(left) + 1.2),
        )
        axis.invert_yaxis()
        axis.grid(visible=True, axis="x", which="major", color=".9", lw=0.5)
        axis.set_axisbelow(True)
        figure.legend(loc="lower center", ncol=2, frameon=False, fontsize=8.5)
        figure.savefig(output, metadata={"CreationDate": None})
        plt.close(figure)


def _ablation_figure(
    points: pd.DataFrame, variants: dict[str, HMMArtifact], output: Path
) -> dict:
    """Display the previously used regression flight, explicitly outside validation."""
    import matplotlib.pyplot as plt

    decoded = {
        name: _phase_points(points, artifact) for name, artifact in variants.items()
    }
    counts = {
        name: frame["phase"].value_counts().to_dict() for name, frame in decoded.items()
    }
    origin = float(points.t.iloc[0])
    keep = (points.t >= origin + 1500) & (points.t <= origin + 1980)
    time = (points.loc[keep, "t"].to_numpy() - origin) / 60
    with plt.rc_context({"pdf.fonttype": 42}):
        figure, axes = plt.subplots(
            5,
            1,
            figsize=(6.1, 4.9),
            sharex=True,
            gridspec_kw={"height_ratios": [1.25, 1, 0.35, 0.35, 0.35]},
        )
        figure.subplots_adjust(
            left=0.21, right=0.97, top=0.92, bottom=0.17, hspace=0.28
        )
        axes[0].plot(time, points.loc[keep, "z"], color="#333333")
        axes[0].set_ylabel("Altitude\n(m)")
        axes[1].plot(time, points.loc[keep, "mean_v_z"], color=TRACE_COLOR)
        axes[1].axhline(0, color=".6", linestyle="--", linewidth=0.8)
        axes[1].set_ylabel("Mean vertical\nspeed (m/s)")
        for axis, (name, frame) in zip(axes[2:], decoded.items(), strict=True):
            phases = frame.loc[keep, "phase"].to_numpy()
            boundaries = np.r_[
                0, np.flatnonzero(phases[1:] != phases[:-1]) + 1, len(phases)
            ]
            for first, stop in pairwise(boundaries):
                axis.axvspan(
                    time[first] - 1 / 12,
                    time[stop - 1] + 1 / 12,
                    color=PALETTE.get(phases[first], "#999999"),
                    linewidth=0,
                )
            axis.set(ylabel=name, yticks=[])
            axis.yaxis.label.set(rotation=0, ha="right", va="center")
        for axis in axes:
            axis.spines[["top", "right"]].set_visible(False)
        axes[-1].set(
            xlabel="Time from cleaned-segment start (min)", xlim=(time[0], time[-1])
        )
        from matplotlib.patches import Patch

        figure.legend(
            handles=[Patch(color=c, label=s) for s, c in PALETTE.items()],
            loc="lower center",
            ncol=3,
            frameon=False,
        )
        figure.suptitle(
            "Flight 20311250: development example, not manual validation", fontsize=11
        )
        figure.savefig(output, metadata={"CreationDate": None})
        plt.close(figure)
    return {
        "flight_id": "20311250",
        "split": "train",
        "counts_full_segment": counts,
        "display_elapsed_s": [1500, 1980],
    }


def main(argv: list[str] | None = None) -> int:
    """Write figures, finite audit counts and immutable-input provenance."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/segmentation.yaml"
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        help="Count reference intervals from an explicitly chosen matching pack",
    )
    args = parser.parse_args(argv)
    config = load_segmentation_config(args.config)
    generated = ROOT / "thesis/generated"
    generated.mkdir(exist_ok=True)
    audit: dict = {
        "purpose": "Current-decoder diagnostics; no independent manual accuracy",
        "config": asdict(config),
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "disciplines": {},
        "annotations_path": str(args.annotations.resolve())
        if args.annotations
        else None,
    }
    artifacts = {}
    coverages = {}
    table = [
        r"% Generated by scripts/reporting/ch4_flight_phases/"
        r"generate_decoder_audit.py; no accuracy implied.",
        r"\begin{table}[tb]",
        r"\centering\small",
        r"\caption{Support and numerical diagnostics of the segmentation. "
        r"Excluded time uses all retained cleaned-segment duration as its "
        r"denominator. Coherence widths belong to the original four-dimensional "
        r"climb component.}",
        r"\label{tab:segmentationaudit}",
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"Quantity & Paragliders & Hang gliders \\",
        r"\midrule",
    ]
    for name, discipline in DISCIPLINES.items():
        derived = discipline.derived_dir(require="segmentation/phase_points.parquet")
        if derived is None:
            raise FileNotFoundError(f"{name}: archive unavailable")
        root = derived / "segmentation"
        saved = HMMArtifact.load(root / "model")
        legacy = reference_artifact(saved)
        current = current_artifact(saved, config)
        artifacts[name] = current
        points = _validation_example(root)
        fresh = _phase_points(points, current)
        plot_phase_trajectory(
            fresh,
            generated / f"segmentation_current_example_{discipline.slug}.pdf",
            duration_s=480,
            coherence_in_emissions=False,
        )
        plot_model_diagnostics(
            current, generated / f"segmentation_current_model_{discipline.slug}.pdf"
        )
        archived_recomputed = _phase_points(points, saved)
        if not np.array_equal(
            archived_recomputed["phase"].to_numpy(), points["phase"].to_numpy()
        ):
            raise ValueError(
                f"{name}: stored features no longer reproduce archived phases"
            )
        classified = points.phase != "unclassified"
        legacy_recomputed = _phase_points(points, legacy)
        differences = int(
            np.sum(
                fresh.loc[classified, "phase"].to_numpy()
                != legacy_recomputed.loc[classified, "phase"].to_numpy()
            )
        )
        climb = next(k for k, v in current.state_mapping.items() if v == "climb")
        coherence_mean = float(
            current.model.means_[climb, 3] * current.scaler.scale[3]
            + current.scaler.mean[3]
        )
        coherence_sd = float(
            np.sqrt(current.model.covars_[climb, 3, 3]) * current.scaler.scale[3]
        )
        coverage = json.loads((root / "coverage_summary.json").read_text())
        coverages[name] = coverage
        history = np.asarray(saved.model.monitor_.history, dtype=float)
        gain = float(history[-1] - history[-2]) if history.size >= 2 else None
        audit["disciplines"][name] = {
            "model_metadata_sha256": hashlib.sha256(
                (root / "model/metadata.json").read_bytes()
            ).hexdigest(),
            "model_pickle_sha256": hashlib.sha256(
                (root / "model/gaussian_hmm.pkl").read_bytes()
            ).hexdigest(),
            "fit_observations": legacy.n_fit_observations,
            "fit_sequences": legacy.n_fit_sequences,
            "selected_restart_diagnostics": {
                "iterations": saved.model.monitor_.iter,
                "iteration_cap": saved.model.n_iter,
                "last_log_likelihood_gain": gain,
                "nonnegative_gain_below_tolerance": (
                    gain is not None and 0 <= gain < saved.config.tol
                ),
                "minimum_covariance_eigenvalue": float(
                    np.linalg.eigvalsh(saved.model.covars_).min()
                ),
            },
            "archive_decoder_matches_current": saved.config == config,
            "archive_feature_support": saved.feature_support,
            "fitted_transition_matrix": _ordered_matrix(current, fitted=True).tolist(),
            "decoding_transition_matrix": _ordered_matrix(
                current, fitted=False
            ).tolist(),
            "climb_coherence_mean": coherence_mean,
            "climb_coherence_sd": coherence_sd,
            "coverage": coverage,
            "example": {
                "source": str(points.source.iloc[0]),
                "flight_id": str(points.flight_id.iloc[0]),
                "segment_id": int(points.segment_id.iloc[0]),
                "split": "validation",
                "selection": (
                    "first classifiable segment by ascending validation "
                    "manifest priority"
                ),
                "full_decisions": len(points),
                "classified_decisions": int(classified.sum()),
                "changed_decisions": differences,
                "stored_archive_path_reproduced": True,
                "display_duration_s": 480,
                "counts_current": fresh.phase.value_counts().to_dict(),
                "feature_hash": hashlib.sha256(
                    pd.util.hash_pandas_object(
                        points[["t", *FEATURE_COLUMNS]], index=False
                    ).values.tobytes()
                ).hexdigest(),
            },
            "current_full_archive_export_exists": saved.config == config,
        }
        if name == "paragliders":
            regression = pd.read_parquet(
                root / "phase_points.parquet", filters=[("flight_id", "==", "20311250")]
            )
            regression = (
                regression.loc[regression.segment_id == regression.segment_id.min()]
                .sort_values("t")
                .reset_index(drop=True)
            )
            sequence_only = replace(
                current,
                config=replace(current.config, marginalize_turn_coherence=False),
            )
            audit["development_ablation"] = _ablation_figure(
                regression,
                {
                    "Fitted 4D": legacy,
                    "Prior only": sequence_only,
                    "Current 3D": current,
                },
                generated / "segmentation_decoder_ablation.pdf",
            )
        print(
            f"{name}: current example {points.flight_id.iloc[0]}, "
            f"{differences}/{classified.sum()} decisions differ "
            "from fitted 4D reference"
        )
    records = list(audit["disciplines"].values())
    rows = [
        (
            "Emitted archive decisions",
            [tex_int(r["coverage"]["n_decision_points"]) for r in records],
        ),
        (
            "Excluded cleaned duration",
            [
                f"{r['coverage']['unclassified_duration_percent']:.2f}\\%"
                for r in records
            ],
        ),
        (
            r"Climb $C_\omega$ mean (original fit)",
            [f"{r['climb_coherence_mean']:.7f}" for r in records],
        ),
        (
            r"Climb $C_\omega$ standard deviation",
            [f"{r['climb_coherence_sd']:.7f}" for r in records],
        ),
        (
            "Final EM log-likelihood change",
            [
                f"{r['selected_restart_diagnostics']['last_log_likelihood_gain']:.3g}"
                for r in records
            ],
        ),
        ("Annotated intervals supplied", ["0", "0"]),
    ]
    annotations = (
        pd.read_csv(args.annotations)
        if args.annotations
        else pd.DataFrame(columns=["source"])
    )
    rows[-1] = (
        "Annotated intervals supplied",
        [
            str(int((annotations.source == d.source).sum()))
            for d in DISCIPLINES.values()
        ],
    )
    for label, values in rows:
        table.append(label + " & " + " & ".join(values) + r" \\")
    table.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (generated / "segmentation_audit_table.tex").write_text("\n".join(table) + "\n")
    values = [
        "% Generated by scripts/reporting/ch4_flight_phases/generate_decoder_audit.py; match the audited snapshot."
    ]
    for discipline, record in zip(DISCIPLINES.values(), records, strict=True):
        tag = discipline.tag
        quantities = {
            f"SegAudit{tag}CoherenceSD": f"{record['climb_coherence_sd']:.7f}",
            f"SegAudit{tag}ExcludedPct": (
                f"{record['coverage']['unclassified_duration_percent']:.2f}"
            ),
        }
        for name, value in quantities.items():
            values.append("\\newcommand{\\" + name + "}{" + value + "}")
    counts = audit["development_ablation"]["counts_full_segment"]
    for variant, tag in (
        ("Fitted 4D", "Reference"),
        ("Prior only", "Prior"),
        ("Current 3D", "Current"),
    ):
        values.append(
            r"\newcommand{\SegAudit"
            + tag
            + "Climb}{"
            + str(counts[variant].get("climb", 0))
            + "}"
        )
    is_current = all(r["archive_decoder_matches_current"] for r in records)
    values.append(
        r"\newcommand{\SegAuditArchiveStatus}{"
        + (
            "The saved archive uses the current decoder. The four-dimensional path "
            "is reconstructed from the same fitted parameters as a comparison."
            if is_current
            else "The saved archive still uses the earlier four-dimensional decoder. "
            "Current labels in this chapter are recomputed from its saved features."
        )
        + "}"
    )
    full_support = all(
        r["archive_feature_support"] == "includes propagated SG reconstruction support"
        for r in records
    )
    values.append(
        r"\newcommand{\SegAuditSupportStatus}{"
        + (
            "The feature masks include the propagated reconstruction support of the "
            "vertical Savitzky--Golay derivatives."
            if full_support
            else "These counts describe the earlier reconstruction mask, which did "
            "not propagate the vertical smoothing support. They must be regenerated "
            "after the corrected cleaning and feature extraction are applied."
        )
        + "}"
    )
    fit_converged = all(
        r["selected_restart_diagnostics"]["nonnegative_gain_below_tolerance"]
        for r in records
    )
    values.append(
        r"\newcommand{\SegAuditFitStatus}{"
        + (
            "Both selected restarts have a finite, non-negative final likelihood gain "
            "below the stopping tolerance. This is a numerical stopping check, "
            "not evidence of a global optimum."
            if fit_converged
            else "The selected fits do not both satisfy a finite, non-negative "
            "last gain below tolerance (Table~\\ref{tab:segmentationaudit}). "
            "The software stopping flags therefore cannot establish convergence of "
            "these fits; covariance and refitting sensitivity remain to be checked."
        )
        + "}"
    )
    values.append(
        r"\newcommand{\SegAuditAnnotationStatus}{"
        + (
            "No human reference intervals were supplied to this audit, so it reports "
            "no independent classification scores."
            if annotations.empty
            else "An annotation file was supplied for interval counts. "
            "Independent scores "
            "require the matching-snapshot evaluator and the frozen test protocol."
        )
        + "}"
    )
    (generated / "segmentation_audit_values.tex").write_text("\n".join(values) + "\n")
    _transition_figure(artifacts, generated / "segmentation_decoding_transitions.pdf")
    _coverage_figure(coverages, generated / "segmentation_coverage.pdf")
    (generated / "segmentation_decoder_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
