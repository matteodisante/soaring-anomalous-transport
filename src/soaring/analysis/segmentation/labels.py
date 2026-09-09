"""Manual-label contracts, state naming, and flight-clustered validation metrics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

STATES = ("transition", "search", "climb")
ANNOTATION_COLUMNS = [
    "source",
    "flight_id",
    "segment_id",
    "t_start",
    "t_end",
    "state",
    "split",
    "annotator",
]
_IDENTITY_COLUMNS = ["source", "flight_id", "segment_id"]
_SPLITS = {"train", "validation", "test"}


def validate_annotations(annotations: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize the manual interval-annotation table.

    Labels identify homogeneous half-open intervals ``[t_start, t_end)``, not single
    fixes.  Touching intervals are therefore allowed, while overlapping intervals within
    one preprocessing segment are refused because a decision time must have one
    unambiguous ground-truth state.

    Args:
        annotations: Candidate annotation table.

    Returns:
        A copy in the canonical column order.

    Raises:
        ValueError: If required values, state names, split names, or interval bounds are
            invalid.
    """
    missing = set(ANNOTATION_COLUMNS).difference(annotations.columns)
    if missing:
        raise ValueError(f"annotation table is missing columns: {sorted(missing)}")
    out = annotations[ANNOTATION_COLUMNS].copy()
    non_interval = out.drop(columns=["t_start", "t_end"])
    if non_interval.isna().any().any():
        raise ValueError("manual annotations must have no missing values")
    # A flight identifier can look numeric in a CSV and is therefore easily inferred as
    # an integer by Pandas, while the IGC-derived Parquet table intentionally preserves
    # it as an identifier. Normalize identity types before any joins.
    out["source"] = out["source"].astype("string")
    out["flight_id"] = out["flight_id"].astype("string")
    try:
        segment_ids = pd.to_numeric(out["segment_id"], errors="raise")
    except (TypeError, ValueError) as error:
        raise ValueError("annotation segment_id values must be integers") from error
    numeric_segment_ids = segment_ids.to_numpy(dtype=float)
    if (
        not np.isfinite(numeric_segment_ids).all()
        or not np.equal(numeric_segment_ids, np.floor(numeric_segment_ids)).all()
    ):
        raise ValueError("annotation segment_id values must be finite integers")
    out["segment_id"] = segment_ids.astype(int)
    out["t_start"] = out["t_start"].astype(float)
    out["t_end"] = out["t_end"].astype(float)
    if not np.isfinite(out[["t_start", "t_end"]].to_numpy(dtype=float)).all():
        raise ValueError("annotation interval bounds must be finite")
    if (out["t_end"] <= out["t_start"]).any():
        raise ValueError("each annotation must have t_end greater than t_start")
    unknown_states = set(out["state"]) - set(STATES)
    if unknown_states:
        raise ValueError(f"unknown phase labels: {sorted(unknown_states)}")
    unknown_splits = set(out["split"]) - _SPLITS
    if unknown_splits:
        raise ValueError(f"unknown annotation splits: {sorted(unknown_splits)}")

    for _, group in out.sort_values([*_IDENTITY_COLUMNS, "t_start"]).groupby(
        _IDENTITY_COLUMNS, sort=False
    ):
        starts = group["t_start"].to_numpy()
        ends = group["t_end"].to_numpy()
        if len(starts) > 1 and np.any(starts[1:] < ends[:-1]):
            raise ValueError("manual phase annotations cannot overlap")
    return out


def load_annotations(path: str) -> pd.DataFrame:
    """Read and validate a CSV or Parquet annotation table."""
    source = str(path)
    frame = (
        pd.read_parquet(source) if source.endswith(".parquet") else pd.read_csv(source)
    )
    return validate_annotations(frame)


def labels_for_points(
    points: pd.DataFrame, annotations: pd.DataFrame, *, split: str | None = None
) -> pd.Series:
    """Align interval labels to decision points, returning nullable phase names.

    Args:
        points: Segmentation rows with identity and ``t`` columns.
        annotations: Validated manual intervals.
        split: Optional annotation split to use.

    Returns:
        A string Series aligned with ``points``; unlabeled points contain ``pd.NA``.
    """
    required = {*_IDENTITY_COLUMNS, "t"}
    missing = required.difference(points.columns)
    if missing:
        raise ValueError(f"phase points are missing columns: {sorted(missing)}")
    checked = validate_annotations(annotations)
    if split is not None:
        if split not in _SPLITS:
            raise ValueError(f"unknown annotation split {split!r}")
        checked = checked.loc[checked["split"] == split]

    result = pd.Series(pd.NA, index=points.index, dtype="string")
    for identity, point_group in points.groupby(_IDENTITY_COLUMNS, sort=False):
        chosen = checked
        for column, value in zip(_IDENTITY_COLUMNS, identity, strict=True):
            if column in {"source", "flight_id"}:
                chosen = chosen.loc[chosen[column] == str(value)]
            else:
                chosen = chosen.loc[chosen[column] == value]
        for label in chosen.itertuples(index=False):
            matched = point_group.index[
                (point_group["t"] >= label.t_start) & (point_group["t"] < label.t_end)
            ]
            if result.loc[matched].notna().any():
                raise ValueError("multiple manual labels matched one phase point")
            result.loc[matched] = label.state
    return result


def semantic_mapping(
    raw_states: Iterable[int], labels: Iterable[str]
) -> dict[int, str]:
    """Solve HMM label switching by maximum-overlap one-to-one assignment.

    A per-column majority rule can assign two raw HMM states to the same behavioural
    phase.  The Hungarian assignment instead finds the single permutation maximizing
    agreement with train-only manual annotations.
    """
    from scipy.optimize import linear_sum_assignment

    raw = np.asarray(list(raw_states), dtype=int)
    truth = np.asarray(list(labels), dtype=str)
    if raw.size != truth.size or raw.size == 0:
        raise ValueError(
            "state mapping needs equally sized non-empty predictions and labels"
        )
    if np.any(~np.isin(truth, STATES)):
        raise ValueError("state mapping received an unknown manual state")
    if set(truth) != set(STATES):
        raise ValueError(
            "state mapping needs at least one train annotation for every phase"
        )
    components = np.unique(raw)
    if components.size != len(STATES):
        raise ValueError("state mapping requires all three HMM components")
    counts = np.zeros((len(STATES), len(STATES)), dtype=int)
    for row, component in enumerate(components):
        for col, state in enumerate(STATES):
            counts[row, col] = int(np.sum((raw == component) & (truth == state)))
    rows, cols = linear_sum_assignment(-counts)
    if np.any(counts[rows, cols] == 0):
        raise ValueError(
            "state mapping needs train labels that support every assigned component"
        )
    return {
        int(components[row]): STATES[col] for row, col in zip(rows, cols, strict=True)
    }


@dataclass(frozen=True)
class ClassificationMetrics:
    """Sample-level classification metrics, reported with a clustered macro average."""

    accuracy: float
    macro_f1: float
    per_state: dict[str, dict[str, float]]
    n_points: int
    n_flights: int


def classification_metrics(
    truth: Iterable[str], prediction: Iterable[str], flight_ids: Iterable[object]
) -> ClassificationMetrics:
    """Calculate phase metrics without treating missing labels as a class."""
    y_true = np.asarray(list(truth), dtype=str)
    y_pred = np.asarray(list(prediction), dtype=str)
    flights = np.asarray(list(flight_ids))
    if y_true.size == 0 or y_true.size != y_pred.size or y_true.size != flights.size:
        raise ValueError(
            "metrics need equally sized non-empty labels, predictions, and flights"
        )
    if np.any(~np.isin(y_true, STATES)) or np.any(~np.isin(y_pred, STATES)):
        raise ValueError("metrics received an unknown phase")
    per_state: dict[str, dict[str, float]] = {}
    f1_values = []
    for state in STATES:
        true_positive = np.sum((y_true == state) & (y_pred == state))
        false_positive = np.sum((y_true != state) & (y_pred == state))
        false_negative = np.sum((y_true == state) & (y_pred != state))
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        f1 = 2.0 * precision * recall / max(np.finfo(float).eps, precision + recall)
        per_state[state] = {"precision": precision, "recall": recall, "f1": f1}
        f1_values.append(f1)
    return ClassificationMetrics(
        accuracy=float(np.mean(y_true == y_pred)),
        macro_f1=float(np.mean(f1_values)),
        per_state=per_state,
        n_points=int(y_true.size),
        n_flights=int(np.unique(flights).size),
    )


def bootstrap_macro_f1(
    truth: Iterable[str],
    prediction: Iterable[str],
    flight_ids: Iterable[object],
    *,
    seed: int,
    replicates: int,
) -> tuple[float, float]:
    """Return a 95% flight-cluster bootstrap interval for macro-F1."""
    y_true = np.asarray(list(truth), dtype=str)
    y_pred = np.asarray(list(prediction), dtype=str)
    flights = np.asarray(list(flight_ids))
    unique = np.unique(flights)
    if unique.size == 0:
        raise ValueError("bootstrap needs at least one labelled flight")
    generator = np.random.default_rng(seed)
    scores = np.empty(replicates, dtype=float)
    for rep in range(replicates):
        drawn = generator.choice(unique, size=unique.size, replace=True)
        indexes = np.concatenate(
            [np.flatnonzero(flights == flight) for flight in drawn]
        )
        scores[rep] = classification_metrics(
            y_true[indexes], y_pred[indexes], flights[indexes]
        ).macro_f1
    bounds = np.quantile(scores, [0.025, 0.975])
    return float(bounds[0]), float(bounds[1])
