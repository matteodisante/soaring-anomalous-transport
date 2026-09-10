"""Explicit denominators and reasons for segmentation coverage."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


def decision_reasons(points: pd.DataFrame) -> np.ndarray:
    """Partition decisions into classified, feature edge, quality mask, or other."""
    reasons = np.where(
        points["phase"].eq("unclassified"), "unavailable_features", "classified"
    )
    missing = points["phase"].eq("unclassified").to_numpy()
    for flag in ("quality_masked", "feature_edge"):
        if flag in points:
            reasons[missing & points[flag].fillna(False).to_numpy(dtype=bool)] = flag
    return reasons


def native_coverage_summary(fixes: pd.DataFrame) -> dict:
    """Count displayed cleaned fixes, and left-labelled edges within physical runs.

    Counts refer to fixes, not flights or HMM confidence. The duration denominator
    excludes acquisition gaps; each native edge takes its starting fix's colour.
    """
    counts = fixes["phase_reason"].value_counts().to_dict()
    seconds: defaultdict[str, float] = defaultdict(float)
    for _, run in fixes.groupby("track_run", sort=False):
        dt = np.diff(run["t"].to_numpy(dtype=float))
        reasons = run["phase_reason"].to_numpy()[:-1]
        for reason in np.unique(reasons):
            seconds[str(reason)] += float(dt[reasons == reason].sum())
    n = len(fixes)
    total_s = sum(seconds.values())
    return {
        "n_cleaned_fixes": n,
        "unclassified_fix_percent": 100 * (n - counts.get("classified", 0)) / n
        if n
        else None,
        "fixes_by_reason": {str(k): int(v) for k, v in counts.items()},
        "cleaned_duration_s": total_s,
        "unclassified_duration_percent": 100
        * (total_s - seconds["classified"])
        / total_s
        if total_s
        else None,
        "seconds_by_reason": dict(seconds),
    }


def archive_coverage_summary(directory: str | Path) -> dict:
    """Stream decisions and measure coverage over all cleaned segment durations.

    Decision percentages exclude segments too slow to enter the decision grid.
    Duration percentages include them, clipping each decision cell at the cleaned
    segment boundaries. Remaining tails have no decision cell and remain uncovered.
    No multi-gigabyte trajectory table is loaded into memory.
    """
    import pyarrow.parquet as pq

    from .model import HMMArtifact

    root = Path(directory)
    artifact = HMMArtifact.load(root / "model")
    step = artifact.config.decision_step_s
    coverage = pd.read_parquet(root / "phase_coverage.parquet")
    identity = ["source", "flight_id", "segment_id"]
    bounds = coverage.set_index(identity)[["t_start", "t_end"]]
    if not bounds.index.is_unique:
        raise ValueError("coverage must contain one row per preprocessing segment")
    duration = coverage["t_end"] - coverage["t_start"]
    skipped = coverage["status"].eq("skipped_native_cadence")
    seconds: defaultdict[str, float] = defaultdict(
        float, {"skipped_native_cadence": float(duration[skipped].sum())}
    )
    counts: Counter = Counter()
    columns = [*identity, "t", "phase", "feature_edge", "quality_masked"]
    for batch in pq.ParquetFile(root / "phase_points.parquet").iter_batches(
        columns=columns
    ):
        points = batch.to_pandas()
        selected = bounds.reindex(pd.MultiIndex.from_frame(points[identity]))
        if selected.isna().any().any():
            raise ValueError("decision identities are missing from phase coverage")
        t = points["t"].to_numpy(dtype=float)
        weights = np.maximum(
            0,
            np.minimum(t + step / 2, selected.t_end.to_numpy())
            - np.maximum(t - step / 2, selected.t_start.to_numpy()),
        )
        reasons = decision_reasons(points)
        for reason in np.unique(reasons):
            mask = reasons == reason
            counts[str(reason)] += int(mask.sum())
            seconds[str(reason)] += float(weights[mask].sum())
    n = sum(counts.values())
    if n != int(coverage.n_decision_points.sum()) or counts["classified"] != int(
        coverage.n_classifiable_points.sum()
    ):
        raise ValueError(
            "point and coverage tables disagree; regenerate matching outputs"
        )
    total_s = float(duration.sum())
    remaining = total_s - sum(seconds.values())
    if remaining < -1e-5 * max(1, total_s):
        raise ValueError("decision cells exceed cleaned segment duration")
    seconds["outside_decision_cells"] = max(0.0, remaining)
    return {
        "directory": str(root),
        "sequence_prior_weight": artifact.config.sequence_prior.weight,
        "n_cleaned_segments": len(coverage),
        "n_cleaned_fixes": int(coverage.n_native_fixes.sum()),
        "n_decision_points": n,
        "unclassified_decision_percent": 100 * (n - counts["classified"]) / n
        if n
        else None,
        "decisions_by_reason": dict(counts),
        "cleaned_duration_s": total_s,
        "unclassified_duration_percent": 100
        * (total_s - seconds["classified"])
        / total_s
        if total_s
        else None,
        "seconds_by_reason": dict(seconds),
    }
