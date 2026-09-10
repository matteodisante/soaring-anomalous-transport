#!/usr/bin/env python3
"""Select diverse held-out phase windows and build a blinded annotation pack.

The pack deliberately contains kinematics but no HMM predictions.  It is therefore
usable as independent ground truth even though its candidate flights are selected from
the already fixed flight-level split manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from soaring.analysis.segmentation.features import FEATURE_COLUMNS  # noqa: E402
from soaring.reporting import DISCIPLINES  # noqa: E402

PACK_COLUMNS = [
    "candidate_id",
    "discipline",
    "source",
    "flight_id",
    "segment_id",
    "split",
    "window_start",
    "window_end",
    "complete_segment",
    "season_year",
    "date",
    "takeoff",
    "duration_flight_s",
    "path_km",
    "alt_range_m",
    "dt_native_s",
]
POINT_COLUMNS = [
    "source",
    "flight_id",
    "segment_id",
    "t",
    "E",
    "N",
    "z",
    "feature_edge",
    "quality_masked",
    *FEATURE_COLUMNS,
    "phase",
]


def _catalog(derived: Path) -> pd.DataFrame:
    """Read only non-sensitive fields used for coverage and figure context."""
    path = derived.parent / "catalog" / "catalog.csv"
    if not path.is_file():
        return pd.DataFrame(columns=["flight_id", "season_year", "date", "takeoff"])
    frame = pd.read_csv(
        path,
        usecols=lambda name: name in {"flight_id", "season_year", "date", "takeoff"},
        low_memory=False,
    )
    frame["flight_id"] = frame["flight_id"].astype("string")
    return frame.drop_duplicates("flight_id")


def _eligible_segments(derived: Path) -> pd.DataFrame:
    """Join coverage, split, flight, and season metadata without reading point rows."""
    root = derived / "segmentation"
    coverage = pd.read_parquet(root / "phase_coverage.parquet")
    manifest = pd.read_parquet(root / "model" / "split_manifest.parquet")
    meta_columns = [
        "source",
        "flight_id",
        "duration_flight_s",
        "path_km",
        "alt_range_m",
        "lat0",
        "lon0",
        "dt_native_s",
    ]
    metadata = pd.read_parquet(derived / "flights_meta.parquet", columns=meta_columns)
    for frame in (coverage, manifest, metadata):
        frame["source"] = frame["source"].astype("string")
        frame["flight_id"] = frame["flight_id"].astype("string")
    eligible = coverage.loc[
        (coverage["status"] == "decoded")
        & (coverage["n_classifiable_points"] >= 180)
        & ((coverage["t_end"] - coverage["t_start"]) >= 1800.0)
    ].copy()
    eligible = eligible.sort_values(
        ["source", "flight_id", "n_classifiable_points"],
        ascending=[True, True, False],
    ).drop_duplicates(["source", "flight_id"])
    eligible = eligible.merge(
        manifest[["source", "flight_id", "split", "priority"]],
        on=["source", "flight_id"],
        validate="one_to_one",
    ).merge(
        metadata,
        on=["source", "flight_id"],
        validate="one_to_one",
    )
    return eligible.merge(_catalog(derived), on="flight_id", how="left")


def _diverse_rows(
    frame: pd.DataFrame, count: int, *, prefer_short: bool
) -> pd.DataFrame:
    """Use deterministic farthest-point sampling over conditions and seasons."""
    candidates = frame.copy()
    if prefer_short and len(candidates) > 2 * count:
        cutoff = candidates["duration_flight_s"].quantile(0.35)
        short = candidates.loc[candidates["duration_flight_s"] <= cutoff]
        if len(short) >= count:
            candidates = short
    fields = [
        "season_year",
        "duration_flight_s",
        "path_km",
        "alt_range_m",
        "lat0",
        "lon0",
        "dt_native_s",
    ]
    values = candidates[fields].astype(float)
    values = values.fillna(values.median()).to_numpy()
    values[:, 1:4] = np.log1p(np.maximum(values[:, 1:4], 0.0))
    center = np.nanmedian(values, axis=0)
    scale = np.nanpercentile(values, 75, axis=0) - np.nanpercentile(values, 25, axis=0)
    scale[~np.isfinite(scale) | (scale <= np.finfo(float).eps)] = 1.0
    standardized = np.clip((values - center) / scale, -4.0, 4.0)
    selected = [int(np.argmin(np.sum(standardized**2, axis=1)))]
    while len(selected) < min(count, len(candidates)):
        distance = np.min(
            np.sum(
                (standardized[:, None, :] - standardized[selected][None, :, :]) ** 2,
                axis=2,
            ),
            axis=1,
        )
        distance[selected] = -np.inf
        selected.append(int(np.argmax(distance)))
    return candidates.iloc[selected].reset_index(drop=True)


def _select_candidates(
    discipline: str,
    derived: Path,
    *,
    train_count: int,
    validation_count: int,
    test_count: int,
) -> pd.DataFrame:
    eligible = _eligible_segments(derived)
    rows = []
    counts = {
        "train": train_count,
        "validation": validation_count,
        "test": test_count,
    }
    for split, count in counts.items():
        chosen = _diverse_rows(
            eligible.loc[eligible["split"] == split],
            count,
            prefer_short=split == "train",
        )
        chosen.insert(0, "discipline", discipline)
        chosen.insert(
            0,
            "candidate_id",
            [
                f"{DISCIPLINES[discipline].slug}-{split[:3]}-{i + 1:02d}"
                for i in range(len(chosen))
            ],
        )
        rows.append(chosen)
    return pd.concat(rows, ignore_index=True)


def _valid_blocks(points: pd.DataFrame) -> list[pd.DataFrame]:
    valid = ~(
        points["feature_edge"].to_numpy(dtype=bool)
        | points["quality_masked"].to_numpy(dtype=bool)
    )
    positions = np.flatnonzero(valid)
    if not positions.size:
        return []
    boundaries = np.flatnonzero(np.diff(positions) > 1) + 1
    return [points.iloc[indexes] for indexes in np.split(positions, boundaries)]


def _window(points: pd.DataFrame, row: pd.Series) -> tuple[float, float, bool]:
    """Choose a complete train segment or a model-blind 30-minute held-out window."""
    blocks = _valid_blocks(points)
    if not blocks:
        raise ValueError(f"{row.candidate_id}: no valid feature block")
    longest = max(blocks, key=len)
    if row["split"] == "train":
        return float(longest["t"].iloc[0]), float(longest["t"].iloc[-1] + 10.0), True
    window_s = min(1800.0, float(longest["t"].iloc[-1] - longest["t"].iloc[0] + 10.0))
    available = max(
        0.0, float(longest["t"].iloc[-1] + 10.0 - longest["t"].iloc[0]) - window_s
    )
    digest = hashlib.sha256(str(row.candidate_id).encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2**64
    start = float(longest["t"].iloc[0]) + available * fraction
    start = 10.0 * round(start / 10.0)
    return start, start + window_s, False


def _candidate_points(
    derived: Path, candidates: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = candidates["flight_id"].astype(str).tolist()
    points = pd.read_parquet(
        derived / "segmentation" / "phase_points.parquet",
        columns=POINT_COLUMNS,
        filters=[("flight_id", "in", ids)],
    )
    points["flight_id"] = points["flight_id"].astype("string")
    output = []
    windows = []
    for _, row in candidates.iterrows():
        selected = points.loc[
            (points["source"].astype(str) == str(row["source"]))
            & (points["flight_id"].astype(str) == str(row["flight_id"]))
            & (points["segment_id"] == row["segment_id"])
        ].sort_values("t", kind="stable")
        start, end, complete = _window(selected, row)
        selected = selected.loc[(selected["t"] >= start) & (selected["t"] < end)].copy()
        selected.insert(0, "candidate_id", row["candidate_id"])
        selected.insert(1, "split", row["split"])
        selected = selected.drop(columns="phase")  # preserve blind manual assessment
        output.append(selected)
        record = row.to_dict()
        record |= {
            "window_start": start,
            "window_end": end,
            "complete_segment": complete,
        }
        windows.append(record)
    return pd.concat(output, ignore_index=True), pd.DataFrame(windows)


def _plot_page(points: pd.DataFrame, row: pd.Series, pdf) -> None:
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(3, 2, figsize=(11.7, 8.3), constrained_layout=True)
    time = points["t"]
    axes[0, 0].plot(points["E"], points["N"], color="#303030", linewidth=0.9)
    axes[0, 0].scatter(
        points["E"].iloc[0], points["N"].iloc[0], color="#4E8A5B", s=25, label="start"
    )
    axes[0, 0].scatter(
        points["E"].iloc[-1], points["N"].iloc[-1], color="#B5482A", s=25, label="end"
    )
    axes[0, 0].set(
        xlabel="east (m)", ylabel="north (m)", aspect="equal", title="Plan view"
    )
    axes[0, 0].legend(frameon=False, fontsize=8)
    axes[0, 1].plot(time, points["z"], color="#303030")
    axes[0, 1].set(
        xlabel="processed time t (s)", ylabel="altitude (m)", title="Altitude"
    )
    axes[1, 0].plot(time, points["mean_v_z"], color="#4E8A5B")
    axes[1, 0].axhline(0.0, color="black", linewidth=0.6)
    axes[1, 0].set(
        xlabel="t (s)", ylabel=r"$\bar v_z$ (m s$^{-1}$)", title="Vertical speed"
    )
    axes[1, 1].plot(time, points["mean_v_h"], color="#3477A8")
    axes[1, 1].set(
        xlabel="t (s)", ylabel=r"$\bar v_h$ (m s$^{-1}$)", title="Horizontal speed"
    )
    axes[2, 0].plot(time, np.degrees(points["mean_abs_turn_rate"]), color="#B5482A")
    axes[2, 0].set(
        xlabel="t (s)", ylabel="absolute turn rate (deg/s)", title="Turning intensity"
    )
    axes[2, 1].plot(time, points["turn_coherence"], color="#4D4D4D")
    axes[2, 1].set(
        xlabel="t (s)",
        ylabel=r"$C_\omega$",
        ylim=(-0.03, 1.03),
        title="Turn-direction coherence",
    )
    figure.suptitle(
        f"{row.candidate_id} | {row.discipline} | {row['split']} | "
        f"flight {row.flight_id}, segment {int(row.segment_id)} | "
        f"label [{row.window_start:.0f}, {row.window_end:.0f}) s",
        fontsize=11,
    )
    pdf.savefig(figure)
    plt.close(figure)


def main(argv: list[str] | None = None) -> int:
    """Create the two-discipline blinded labeling bundle."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "annotations" / "phase_labeling"
    )
    parser.add_argument("--train", type=int, default=4)
    parser.add_argument("--validation", type=int, default=8)
    parser.add_argument("--test", type=int, default=8)
    args = parser.parse_args(argv)
    if min(args.train, args.validation, args.test) < 1:
        parser.error("candidate counts must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_points = []
    all_windows = []
    for discipline, definition in DISCIPLINES.items():
        derived = definition.derived_dir()
        if derived is None:
            raise FileNotFoundError(f"{discipline}: processed archive is unavailable")
        candidates = _select_candidates(
            discipline,
            derived,
            train_count=args.train,
            validation_count=args.validation,
            test_count=args.test,
        )
        points, windows = _candidate_points(derived, candidates)
        all_points.append(points)
        all_windows.append(windows)

    candidate_points = pd.concat(all_points, ignore_index=True)
    windows = pd.concat(all_windows, ignore_index=True)
    candidate_points.to_parquet(
        args.output_dir / "annotation_candidates.parquet", index=False
    )
    windows[PACK_COLUMNS].to_csv(
        args.output_dir / "annotation_windows.csv", index=False
    )
    annotations = args.output_dir / "phase_annotations.csv"
    if not annotations.exists():
        annotations.write_text(
            "source,flight_id,segment_id,t_start,t_end,state,split,annotator\n",
            encoding="utf-8",
        )

    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(args.output_dir / "annotation_pack.pdf") as pdf:
        for _, row in windows.iterrows():
            selected = candidate_points.loc[
                candidate_points["candidate_id"] == row.candidate_id
            ]
            _plot_page(selected, row, pdf)
    print(
        f"wrote blinded annotation pack with {len(windows)} candidate windows "
        f"to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
