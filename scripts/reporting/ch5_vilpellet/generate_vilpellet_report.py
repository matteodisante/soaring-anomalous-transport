#!/usr/bin/env python3
"""Measure the transcribed Vilpellet segmenter against the Chapter 4 decoder.

One named flight is decoded twice, by the Gaussian hidden Markov model of Chapter 4 and
by the transcribed binary-feature model of Chapter 5, on exactly the same cleaned
geometry.  From that single comparison the script writes the plan-view figure the
chapter prints, an altitude timeline under the Vilpellet labels, every fixed constant of
the model as a LaTeX macro, and a JSON record of where each number came from.

Nothing here is fitted or tuned.  The constants are read out of
``configs/segmentation_vilpellet.yaml`` so that editing the configuration moves the
thesis text with it, and the measured numbers come from the two decoders run in front
of the reader.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
# Static output contract for the provenance checker; paths may be built dynamically.
GENERATED_OUTPUTS = (
    "ch5_vilpellet_comparison.pdf",
    "ch5_vilpellet_example.pdf",
    "ch5_vilpellet_values.tex",
    "ch5_vilpellet.json",
)

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from soaring.analysis.segmentation.vilpellet import (  # noqa: E402
    UNCLASSIFIED,
    VilpelletConfig,
    load_vilpellet_config,
    phase_runs,
    segment_flight,
)
from soaring.analysis.segmentation.vilpellet.figures import (  # noqa: E402
    make_plan_figure,
    phase_palette,
    plot_feature_timeline,
    plot_placeholder_panel,
    plot_segmentation_comparison,
    save_figure,
)
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    MacroWriter,
    tex_int,
    write_macros,
)
from soaring.reporting.style import TEXT_WIDTH_IN, paper_style  # noqa: E402

GENERATOR = "scripts/reporting/ch5_vilpellet/generate_vilpellet_report.py"
CONFIG_PATH = ROOT / "configs" / "segmentation_vilpellet.yaml"
DEFAULT_IGC = Path(
    "/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/raw/igc/2021-2022/"
    "2021-09-01_20308851.igc"
)
GAUSSIAN_TITLE = "Chapter 4: Gaussian HMM"
VILPELLET_TITLE = "Chapter 5: Vilpellet decoder"
UNREACHABLE_PANEL = (
    "The Chapter 4 model directory is not\nreachable from this machine, so the\n"
    "Gaussian labelling could not be decoded\nfor this figure."
)

# Digits cannot appear in a LaTeX control sequence, so the spelled-out names below are
# what the thesis quotes.  The values themselves are unconstrained.
_SPELLED_DIGITS = {0: "Zero", 1: "One", 2: "Two"}


def _code_version() -> str:
    """The commit this run was produced from, or a stated fallback.

    Returns:
        The short commit hash, with ``-dirty`` appended when the working tree carries
        uncommitted changes, or ``"unknown"`` when git cannot answer.
    """
    try:
        head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{head}-dirty" if dirty else head


def _fix_durations(points: pd.DataFrame) -> np.ndarray:
    """The time each fix stands for, in seconds.

    A fix accounts for the interval to the next fix of the same physical track.  The
    last fix of a track, and any fix followed by a gap, takes the track's median step
    instead, so the per-phase totals add up to the recorded flight time.

    Args:
        points: A labelled fix table sorted by time, optionally carrying ``track_run``.

    Returns:
        One duration per row.
    """
    t = points["t"].to_numpy(dtype=float)
    if t.size == 0:
        return np.zeros(0, dtype=float)
    steps = np.diff(t)
    if "track_run" in points.columns:
        run = points["track_run"].to_numpy()
        same = run[1:] == run[:-1]
    else:
        same = np.ones(steps.size, dtype=bool)
    usable = np.where(same & (steps > 0), steps, np.nan)
    finite = usable[np.isfinite(usable)]
    median = float(np.median(finite)) if finite.size else 1.0
    return np.r_[np.where(np.isfinite(usable), usable, median), median]


def phase_composition(points: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Fix counts and time fractions of every phase in one labelled flight.

    Args:
        points: A labelled fix table.

    Returns:
        One record per phase name, holding ``n_fixes``, ``fix_fraction``,
        ``duration_s`` and ``time_fraction``.
    """
    durations = _fix_durations(points)
    phases = points["phase"].astype(str).to_numpy()
    total_fixes = len(points)
    total_seconds = float(durations.sum())
    out: dict[str, dict[str, float]] = {}
    for name in sorted(set(phases)):
        mask = phases == name
        seconds = float(durations[mask].sum())
        out[name] = {
            "n_fixes": int(mask.sum()),
            "fix_fraction": float(mask.sum() / total_fixes) if total_fixes else 0.0,
            "duration_s": seconds,
            "time_fraction": seconds / total_seconds if total_seconds else 0.0,
        }
    return out


def classified_runs(points: pd.DataFrame) -> int:
    """Count the uninterrupted runs that carry a phase.

    Unclassified stretches are excluded, so the count means the same thing for both
    segmenters even though one of them leaves fixes unlabelled and the other does not.

    Args:
        points: A labelled fix table carrying ``phase`` and ``phase_run``.

    Returns:
        The number of distinct ``phase_run`` values whose phase is not
        ``unclassified``.
    """
    labelled = points.loc[points["phase"] != UNCLASSIFIED, "phase_run"]
    return int(labelled.nunique())


def agreement(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, Any]:
    """How often two labellings of the same flight name the same phase.

    Only fixes both segmenters classified enter the fraction.  A fix one of them left
    unclassified says nothing about whether they agree, so counting it either way would
    turn a coverage difference into an accuracy claim.

    Args:
        left: One labelled fix table.
        right: The other, holding the same fixes in the same order.

    Returns:
        The common fix count, the agreement fraction, and the confusion counts keyed
        ``"left_phase|right_phase"``, so the first half of a key names the ``left``
        labelling.

    Raises:
        ValueError: If the two tables do not describe the same fixes.
    """
    if len(left) != len(right):
        raise ValueError("the two labellings cover different numbers of fixes")
    if not np.allclose(
        left["t"].to_numpy(dtype=float), right["t"].to_numpy(dtype=float)
    ):
        raise ValueError("the two labellings are not aligned fix by fix")
    left_phase = left["phase"].astype(str).to_numpy()
    right_phase = right["phase"].astype(str).to_numpy()
    common = (left_phase != UNCLASSIFIED) & (right_phase != UNCLASSIFIED)
    confusion: dict[str, int] = {}
    for a, b in zip(left_phase[common], right_phase[common], strict=True):
        key = f"{a}|{b}"
        confusion[key] = confusion.get(key, 0) + 1
    matched = int((left_phase[common] == right_phase[common]).sum())
    return {
        "n_common_fixes": int(common.sum()),
        "n_agreeing_fixes": matched,
        "agreement_fraction": (
            matched / int(common.sum()) if int(common.sum()) else 0.0
        ),
        "confusion": dict(sorted(confusion.items())),
    }


def config_macros(writer: MacroWriter, config: VilpelletConfig) -> None:
    """Record every fixed constant of the model as a macro.

    Args:
        writer: The accumulating macro writer, already carrying the ``Vilp`` prefix.
        config: The loaded protocol.
    """
    features = config.features
    writer.put("PositionSmoothingFixes", features.position_smoothing_fixes)
    writer.put("TurnSmoothingFixes", features.turn_smoothing_fixes)
    writer.put("PersistenceFixes", features.persistence_fixes)
    writer.put("BetaPersistence", f"{features.beta_persistence:g}")
    writer.put("MajorityFixes", config.majority_fixes)
    writer.put("MaxMeanDtSeconds", f"{config.eligibility.max_mean_dt_s:g}")
    writer.put("MinFixes", tex_int(config.eligibility.min_fixes))
    half_window = features.persistence_fixes // 2
    writer.put("TurnSignSelected", half_window)
    writer.put(
        "TurnSignAgreeing", math.ceil(features.beta_persistence * half_window)
    )
    writer.put("ObservationValues", len(config.parameters.emission[0]))
    writer.put("FeatureCount", 3)
    writer.put("StateCount", len(config.state_names))
    writer.put("AlphaPara", f"{config.alpha_for('paragliders'):.8f}")
    writer.put("AlphaHang", f"{config.alpha_for('hang gliders'):.8f}")
    writer.put("AlphaSail", f"{config.alpha_for('sailplanes'):.8f}")
    for component, name in enumerate(config.state_names):
        writer.put(f"Component{_SPELLED_DIGITS[component]}", name)
    writer.put("InputSource", config.input_policy.source)
    writer.put("PreSmooth", "on" if config.input_policy.pre_smooth else "off")


def _percent(record: dict[str, dict[str, float]], phase: str) -> str:
    """One phase's time share of a flight, as a percentage with one decimal."""
    return f"{100.0 * record.get(phase, {}).get('time_fraction', 0.0):.1f}"


def example_macros(
    writer: MacroWriter,
    *,
    flight_id: str,
    discipline: str,
    n_fixes: int,
    duration_s: float,
    alpha: float,
    vilpellet: dict[str, dict[str, float]],
    gaussian: dict[str, dict[str, float]] | None,
    vilpellet_runs: int,
    gaussian_runs: int | None,
    scores: dict[str, Any] | None,
) -> None:
    """Record the measured numbers of the worked example.

    Args:
        writer: The accumulating macro writer.
        flight_id: Identifier of the decoded flight.
        discipline: Its discipline name.
        n_fixes: Cleaned fixes in the flight.
        duration_s: Recorded span of the cleaned flight.
        alpha: The straightness threshold applied.
        vilpellet: Phase composition under the transcribed decoder.
        gaussian: Phase composition under the Chapter 4 decoder, or ``None``.
        vilpellet_runs: Number of uninterrupted runs the transcribed decoder produced.
        gaussian_runs: The same under Chapter 4, or ``None``.
        scores: The output of :func:`agreement`, or ``None``.
    """
    writer.put("ExampleFlight", flight_id.replace("_", r"\_"))
    writer.put("ExampleDiscipline", discipline)
    writer.put("ExampleFixes", tex_int(n_fixes))
    writer.put("ExampleDurationMinutes", f"{duration_s / 60.0:.1f}")
    writer.put("ExampleAlpha", f"{alpha:.8f}")
    writer.put("ExampleRuns", tex_int(vilpellet_runs))
    for phase in ("climb", "search", "transition", UNCLASSIFIED):
        tag = phase.capitalize()
        writer.put(f"ExampleVilp{tag}Percent", _percent(vilpellet, phase))
        writer.put(
            f"ExampleGauss{tag}Percent",
            _percent(gaussian, phase) if gaussian is not None else "n/a",
        )
    writer.put(
        "ExampleGaussRuns",
        tex_int(gaussian_runs) if gaussian_runs is not None else "n/a",
    )
    if scores is None:
        writer.put("ExampleCommonFixes", "n/a")
        writer.put("ExampleAgreementPercent", "n/a")
        writer.put("ExampleComparisonStatus", UNREACHABLE_PANEL.replace("\n", " "))
        return
    writer.put("ExampleCommonFixes", tex_int(scores["n_common_fixes"]))
    writer.put(
        "ExampleAgreementPercent", f"{100.0 * scores['agreement_fraction']:.1f}"
    )
    writer.put(
        "ExampleComparisonStatus",
        "Both decoders labelled this flight, so the agreement fraction below is "
        "measured on the fixes they both classified.",
    )


def build_comparison_figure(
    output: Path,
    gaussian_fixes: pd.DataFrame | None,
    vilpellet_fixes: pd.DataFrame,
    *,
    flight_id: str,
) -> Path:
    """Draw the two plan views the chapter prints, on identical axes.

    Args:
        output: Destination PDF.
        gaussian_fixes: The Chapter 4 labelling, or ``None`` when its model directory
            is out of reach.
        vilpellet_fixes: The transcribed decoder's labelling.
        flight_id: The flight named in the figure title.

    Returns:
        The path written.
    """
    palette = phase_palette()
    figure = make_plan_figure(TEXT_WIDTH_IN, 4.4)
    figure.subplots_adjust(top=0.83, bottom=0.17)
    left = (
        gaussian_fixes if gaussian_fixes is not None else vilpellet_fixes.iloc[0:0]
    )
    left_axis, _right_axis = plot_segmentation_comparison(
        figure,
        left,
        vilpellet_fixes,
        left_title=GAUSSIAN_TITLE,
        right_title=VILPELLET_TITLE,
        color_map=palette,
    )
    if gaussian_fixes is None:
        plot_placeholder_panel(left_axis, UNREACHABLE_PANEL)
    figure.suptitle(
        f"Flight {flight_id}, one cleaned trajectory labelled twice", y=0.975
    )
    return save_figure(figure, output)


def build_example_figure(
    output: Path, vilpellet_fixes: pd.DataFrame, *, flight_id: str
) -> Path:
    """Draw the altitude of one flight with the Vilpellet phase strip beneath it.

    Args:
        output: Destination PDF.
        vilpellet_fixes: The transcribed decoder's labelling.
        flight_id: The flight named in the panel title.

    Returns:
        The path written.
    """
    import matplotlib.pyplot as plt

    figure = plt.figure(figsize=(TEXT_WIDTH_IN, 3.2))
    figure.subplots_adjust(left=0.11, right=0.98, bottom=0.22, top=0.90, hspace=0.12)
    plot_feature_timeline(
        figure,
        vilpellet_fixes,
        column="z",
        ylabel="Altitude (m)",
        title=f"Flight {flight_id}, Vilpellet phases",
        color_map=phase_palette(),
    )
    return save_figure(figure, output)


def main(argv: list[str] | None = None) -> int:
    """Write the four Chapter 5 artefacts from one decoded flight.

    Args:
        argv: Argument vector, or ``None`` to read ``sys.argv``.

    Returns:
        The process exit status.

    Raises:
        FileNotFoundError: If the chosen IGC file is not present.
        ValueError: If cleaning drops the flight, or the transcribed decoder finds it
            ineligible, so there is nothing to compare.
    """
    from soaring.viewer.data import load_cleaned, load_flight_phases

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--igc", type=Path, default=DEFAULT_IGC)
    parser.add_argument(
        "--discipline", choices=list(DISCIPLINES), default="paragliders"
    )
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args(argv)

    paper_style()
    igc_path = Path(args.igc).expanduser()
    if not igc_path.is_file():
        raise FileNotFoundError(f"{igc_path}: no such IGC file")
    discipline = DISCIPLINES[args.discipline]
    flight_id = igc_path.stem
    config = load_vilpellet_config(args.config)

    result = load_cleaned(
        igc_path,
        source=discipline.source,
        flight_id=flight_id,
        discipline=discipline.name,
    )
    if not result.kept:
        raise ValueError(
            f"{flight_id}: dropped at cleaning stage {result.meta.drop_stage}, "
            "so no comparison is possible"
        )
    cleaned = result.fixes
    track = segment_flight(cleaned, config, discipline=discipline.name)
    if not track.eligible:
        raise ValueError(
            f"{flight_id}: ineligible under the Vilpellet gate ({track.reasons})"
        )
    vilpellet_fixes = track.fixes
    vilpellet_runs = phase_runs(vilpellet_fixes, config)

    phase_track = load_flight_phases(cleaned, discipline)
    gaussian_fixes = phase_track.fixes if phase_track is not None else None
    gaussian_composition = (
        phase_composition(gaussian_fixes) if gaussian_fixes is not None else None
    )
    scores = (
        agreement(gaussian_fixes, vilpellet_fixes)
        if gaussian_fixes is not None
        else None
    )
    gaussian_runs = (
        classified_runs(gaussian_fixes) if gaussian_fixes is not None else None
    )
    vilpellet_composition = phase_composition(vilpellet_fixes)

    generated = ROOT / "thesis" / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    comparison_path = build_comparison_figure(
        generated / "ch5_vilpellet_comparison.pdf",
        gaussian_fixes,
        vilpellet_fixes,
        flight_id=flight_id.replace("_", " "),
    )
    example_path = build_example_figure(
        generated / "ch5_vilpellet_example.pdf",
        vilpellet_fixes,
        flight_id=flight_id.replace("_", " "),
    )

    duration_s = float(cleaned["t"].max() - cleaned["t"].min())
    writer = MacroWriter("Vilp")
    config_macros(writer, config)
    example_macros(
        writer,
        flight_id=flight_id,
        discipline=discipline.name,
        n_fixes=len(cleaned),
        duration_s=duration_s,
        alpha=track.alpha_straight_rad,
        vilpellet=vilpellet_composition,
        gaussian=gaussian_composition,
        vilpellet_runs=len(vilpellet_runs),
        gaussian_runs=gaussian_runs,
        scores=scores,
    )
    values_path = generated / "ch5_vilpellet_values.tex"
    n_macros = write_macros(
        values_path,
        writer,
        generator=GENERATOR,
        extra_header=[
            f"Constants read from {args.config.relative_to(ROOT)}.",
            f"Example numbers measured on flight {flight_id}.",
        ],
    )

    import yaml

    record: dict[str, Any] = {
        "generator": GENERATOR,
        "code_version": _code_version(),
        "config_path": str(args.config),
        "config_sha256": hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        "config_values": yaml.safe_load(Path(args.config).read_text(encoding="utf-8")),
        "flight": {
            "flight_id": flight_id,
            "igc_path": str(igc_path),
            "discipline": discipline.name,
            "source": discipline.source,
            "n_cleaned_fixes": len(cleaned),
            "n_segments": int(cleaned["segment_id"].nunique()),
            "duration_s": duration_s,
            "alpha_straight_rad": track.alpha_straight_rad,
        },
        "vilpellet": {
            "phases": vilpellet_composition,
            "n_runs": len(vilpellet_runs),
            "eligible": track.eligible,
            "reasons": track.reasons,
        },
        "gaussian": {
            "available": gaussian_fixes is not None,
            "note": (
                "Chapter 4 labels decoded on demand through "
                "soaring.viewer.data.load_flight_phases."
                if gaussian_fixes is not None
                else "The Chapter 4 model directory was not reachable, so the left "
                "panel of the comparison figure carries a stated placeholder."
            ),
            "phases": gaussian_composition,
            "n_runs": gaussian_runs,
            "mapping_method": (
                phase_track.mapping_method if phase_track is not None else None
            ),
        },
        "agreement": scores,
        "outputs": {
            "comparison_pdf": str(comparison_path),
            "example_pdf": str(example_path),
            "values_tex": str(values_path),
            "n_macros": n_macros,
        },
        "definitions": {
            "time_fraction": (
                "Each fix accounts for the interval to the next fix of the same "
                "physical track; the last fix of a track takes the median step."
            ),
            "agreement_fraction": (
                "Fraction of the fixes both decoders classified on which they name "
                "the same phase."
            ),
            "confusion": (
                "Counts keyed 'chapter4_phase|vilpellet_phase', over the fixes both "
                "decoders classified."
            ),
            "n_runs": (
                "Uninterrupted runs carrying a phase; unclassified stretches are "
                "excluded under both decoders."
            ),
        },
    }
    json_path = generated / "ch5_vilpellet.json"
    json_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

    print(f"{flight_id}: {len(cleaned)} cleaned fixes, {duration_s / 60.0:.1f} min")
    print(f"  wrote {comparison_path.name}, {example_path.name}")
    print(f"  wrote {values_path.name} with {n_macros} macros")
    print(f"  wrote {json_path.name}")
    if scores is not None:
        print(
            f"  agreement on {scores['n_common_fixes']} commonly classified fixes: "
            f"{100.0 * scores['agreement_fraction']:.2f}%"
        )
    else:
        print("  the Chapter 4 model was unreachable; the left panel is a placeholder")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
