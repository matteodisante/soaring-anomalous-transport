"""Streaming train, decode, and evaluation workflow for flight-phase HMMs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from itertools import islice
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..derived import stream_flights
from .config import SegmentationConfig
from .features import (
    FEATURE_COLUMNS,
    build_feature_frame,
    native_cadence_s,
    valid_feature_block_indexes,
    valid_feature_blocks,
    valid_feature_mask,
)
from .labels import (
    STATES,
    ClassificationMetrics,
    bootstrap_macro_f1,
    classification_metrics,
    labels_for_points,
    semantic_mapping,
    validate_annotations,
)
from .model import (
    HMMArtifact,
    decode,
    fit_gaussian_hmm,
    heuristic_state_mapping,
    semantic_states,
)

MANIFEST_COLUMNS = ["source", "flight_id", "split", "priority"]
FIT_SAMPLE_COLUMNS = [
    "source",
    "flight_id",
    "segment_id",
    "sequence_id",
    "priority",
    "n_observations",
    "sample_order",
]
PHASE_POINT_COLUMNS = [
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
    "phase_raw",
    "phase",
    "p_transition",
    "p_search",
    "p_climb",
]
PHASE_SEGMENT_COLUMNS = [
    "source",
    "flight_id",
    "segment_id",
    "phase",
    "t_start",
    "t_end",
    "duration_s",
    "n_points",
    "mean_posterior",
    "left_censored",
    "right_censored",
]
PHASE_COVERAGE_COLUMNS = [
    "source",
    "flight_id",
    "segment_id",
    "t_start",
    "t_end",
    "n_native_fixes",
    "native_cadence_s",
    "n_decision_points",
    "n_classifiable_points",
    "status",
]
_PARQUET_BATCH_ROWS = 100_000
_FEATURE_INPUT_COLUMNS = [
    "source",
    "flight_id",
    "segment_id",
    "t",
    "E",
    "N",
    "z",
    "v_E",
    "v_N",
    "v_z",
    "a_E",
    "a_N",
    "z_reconstructed",
    "edge",
]


def _key(source: object, flight_id: object) -> tuple[str, str]:
    """Make a stable in-memory identity key across Parquet scalar dtypes."""
    return str(source), str(flight_id)


def _priority(source: object, flight_id: object, seed: int) -> int:
    """Stable pseudo-random flight rank independent of archive storage order."""
    payload = f"{seed}|{source}|{flight_id}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def split_for_flight(
    source: object, flight_id: object, config: SegmentationConfig
) -> str:
    """Assign exactly one reproducible train/validation/test split per flight."""
    fraction = _priority(source, flight_id, config.random_seed) / 2**64
    if fraction < config.split.train:
        return "train"
    if fraction < config.split.train + config.split.validation:
        return "validation"
    return "test"


def build_split_manifest(
    fixes_path: str | Path, config: SegmentationConfig
) -> pd.DataFrame:
    """Create a flight-level split manifest without reading the full archive at once."""
    fixes = Path(fixes_path)
    flights_meta = fixes.with_name("flights_meta.parquet")
    if flights_meta.is_file():
        metadata = pd.read_parquet(
            flights_meta,
            columns=["source", "flight_id", "drop_stage", "n_segments_kept"],
        )
        retained = metadata.loc[
            metadata["drop_stage"].isna() & (metadata["n_segments_kept"].fillna(0) > 0),
            ["source", "flight_id"],
        ]
        if retained["flight_id"].duplicated().any():
            raise ValueError(
                "flights_meta contains duplicate retained flight identifiers"
            )
        metadata_rows = [
            {
                "source": row.source,
                "flight_id": row.flight_id,
                "split": split_for_flight(row.source, row.flight_id, config),
                "priority": _priority(row.source, row.flight_id, config.random_seed),
            }
            for row in retained.itertuples(index=False)
        ]
        return pd.DataFrame(metadata_rows, columns=MANIFEST_COLUMNS)

    rows: list[dict[str, object]] = []
    for flight in stream_flights(fixes_path, ["source"]):
        source = flight["source"].iloc[0]
        flight_id = flight["flight_id"].iloc[0]
        rows.append(
            {
                "source": source,
                "flight_id": flight_id,
                "split": split_for_flight(source, flight_id, config),
                "priority": _priority(source, flight_id, config.random_seed),
            }
        )
    return pd.DataFrame(rows, columns=MANIFEST_COLUMNS)


def collect_fit_sample(
    fixes_path: str | Path, manifest: pd.DataFrame, config: SegmentationConfig
) -> tuple[pd.DataFrame, list[np.ndarray]]:
    """Select and materialize the deterministic fitting sample in one archive pass.

    The earlier two-pass implementation first inventoried every eligible block and then
    rescanned the multi-billion-row archive to recover the chosen arrays.  Keeping the
    bounded candidate arrays from the first pass avoids that redundant read.  The final
    sort and whole-sequence observation cap are identical to
    :func:`build_fit_sample_manifest`, so the persisted provenance remains independent
    of Parquet row-group order.
    """
    selected = _selected_train_flights(manifest, config)
    priorities = {
        _key(row.source, row.flight_id): int(row.priority)
        for row in manifest.loc[manifest["split"] == "train"].itertuples(index=False)
        if _key(row.source, row.flight_id) in selected
    }
    candidates: list[tuple[dict[str, Any], np.ndarray]] = []
    for frame in iter_feature_frames(fixes_path, config, allowed_flights=selected):
        source, flight_id = frame["source"].iloc[0], frame["flight_id"].iloc[0]
        key = _key(source, flight_id)
        for sequence_id, values in _bounded_feature_blocks(frame, config):
            candidates.append(
                (
                    {
                        "source": source,
                        "flight_id": flight_id,
                        "segment_id": int(frame["segment_id"].iloc[0]),
                        "sequence_id": sequence_id,
                        "priority": priorities[key],
                        "n_observations": len(values),
                    },
                    values,
                )
            )
    candidates.sort(
        key=lambda item: (
            int(item[0]["priority"]),
            str(item[0]["source"]),
            str(item[0]["flight_id"]),
            int(item[0]["segment_id"]),
            int(item[0]["sequence_id"]),
        )
    )
    chosen_rows: list[dict[str, Any]] = []
    chosen_sequences: list[np.ndarray] = []
    used = 0
    for row, values in candidates:
        count = int(row["n_observations"])
        if used + count > config.max_fit_observations:
            continue
        row["sample_order"] = len(chosen_rows)
        chosen_rows.append(row)
        chosen_sequences.append(values)
        used += count
    if not chosen_rows:
        raise ValueError(
            "the fitting cap cannot accommodate any valid feature sequence"
        )
    return (
        pd.DataFrame(chosen_rows, columns=FIT_SAMPLE_COLUMNS),
        chosen_sequences,
    )


def _selected_train_flights(
    manifest: pd.DataFrame, config: SegmentationConfig
) -> set[tuple[str, str]]:
    """Select a deterministic, flight-balanced subset for in-memory EM fitting."""
    train = manifest.loc[manifest["split"] == "train"].nsmallest(
        config.max_fit_flights, "priority"
    )
    return {_key(row.source, row.flight_id) for row in train.itertuples(index=False)}


def validate_annotation_splits(
    annotations: pd.DataFrame, manifest: pd.DataFrame
) -> pd.DataFrame:
    """Return one archive's annotations after checking its saved split manifest.

    A single annotation file can legitimately carry the two disciplines.  Rows whose
    source is absent from this manifest are therefore outside this archive's scope;
    every in-scope row must be present in the manifest and declare its assigned split.
    This closes the subtle leakage path where an annotator labels a test flight but
    accidentally records it as ``train`` in the interval file.
    """
    checked = validate_annotations(annotations)
    required = {"source", "flight_id", "split"}
    missing = required.difference(manifest.columns)
    if missing:
        raise ValueError(f"split manifest is missing columns: {sorted(missing)}")
    assigned = {
        _key(row.source, row.flight_id): str(row.split)
        for row in manifest[["source", "flight_id", "split"]].itertuples(index=False)
    }
    sources = {source for source, _ in assigned}
    scoped = checked.loc[checked["source"].isin(sources)].copy()
    for row in scoped.itertuples(index=False):
        actual = assigned.get(_key(row.source, row.flight_id))
        if actual is None:
            raise ValueError(
                f"annotation references a flight absent from the split manifest: "
                f"{row.source}/{row.flight_id}"
            )
        if actual != row.split:
            raise ValueError(
                f"annotation split mismatch for {row.source}/{row.flight_id}: "
                f"declared {row.split!r}, manifest has {actual!r}"
            )
    return scoped


def iter_feature_frames(
    fixes_path: str | Path,
    config: SegmentationConfig,
    *,
    allowed_flights: set[tuple[str, str]] | None = None,
) -> Iterator[pd.DataFrame]:
    """Yield one feature frame per preprocessing segment from a streamed fix table."""
    for flight in stream_flights(fixes_path, _FEATURE_INPUT_COLUMNS):
        source, flight_id = flight["source"].iloc[0], flight["flight_id"].iloc[0]
        if (
            allowed_flights is not None
            and _key(source, flight_id) not in allowed_flights
        ):
            continue
        for _, segment in flight.groupby("segment_id", sort=False):
            frame = build_feature_frame(segment, config)
            if not frame.empty:
                yield frame


def _bounded_feature_blocks(
    frame: pd.DataFrame, config: SegmentationConfig
) -> Iterator[tuple[int, np.ndarray]]:
    """Yield whole valid blocks that fit the configured fitting limits.

    A long block is deliberately omitted from this bounded sample rather than cut into
    artificial HMM sequences: cutting would assert a reset of the state process at an
    arbitrary clock time. Its absence remains reproducible through the stored fitting
    sample manifest.
    """
    maximum = min(config.max_sequence_observations, config.max_fit_observations)
    for sequence_id, block in enumerate(valid_feature_blocks(frame)):
        if len(block) <= maximum:
            yield sequence_id, block


def build_fit_sample_manifest(
    fixes_path: str | Path, manifest: pd.DataFrame, config: SegmentationConfig
) -> pd.DataFrame:
    """Select whole valid sequences without exceeding the configured fitting cap.

    This metadata-only first streaming pass fixes the sample independently of Parquet
    row-group order. A second pass then materializes only its selected observations, so
    the advertised observation cap is also a real RAM bound rather than a later
    truncation of an already materialized archive.
    """
    selected = _selected_train_flights(manifest, config)
    priorities = {
        _key(row.source, row.flight_id): int(row.priority)
        for row in manifest.loc[manifest["split"] == "train"].itertuples(index=False)
        if _key(row.source, row.flight_id) in selected
    }
    candidates: list[dict[str, Any]] = []
    for frame in iter_feature_frames(fixes_path, config, allowed_flights=selected):
        source, flight_id = frame["source"].iloc[0], frame["flight_id"].iloc[0]
        key = _key(source, flight_id)
        for sequence_id, values in _bounded_feature_blocks(frame, config):
            candidates.append(
                {
                    "source": source,
                    "flight_id": flight_id,
                    "segment_id": int(frame["segment_id"].iloc[0]),
                    "sequence_id": sequence_id,
                    "priority": priorities[key],
                    "n_observations": len(values),
                }
            )
    candidates.sort(
        key=lambda row: (
            int(row["priority"]),
            str(row["source"]),
            str(row["flight_id"]),
            int(row["segment_id"]),
            int(row["sequence_id"]),
        )
    )
    chosen: list[dict[str, Any]] = []
    used = 0
    for row in candidates:
        count = int(row["n_observations"])
        if used + count > config.max_fit_observations:
            continue
        row["sample_order"] = len(chosen)
        chosen.append(row)
        used += count
    if not chosen:
        raise ValueError(
            "the fitting cap cannot accommodate any valid feature sequence"
        )
    return pd.DataFrame(chosen, columns=FIT_SAMPLE_COLUMNS)


def _fit_sequences(
    fixes_path: str | Path, sample_manifest: pd.DataFrame, config: SegmentationConfig
) -> list[np.ndarray]:
    """Materialize exactly the persisted, whole-sequence fitting sample."""
    missing = set(FIT_SAMPLE_COLUMNS).difference(sample_manifest.columns)
    if missing:
        raise ValueError(f"fit sample manifest is missing columns: {sorted(missing)}")
    selected = {
        _key(row.source, row.flight_id)
        for row in sample_manifest.itertuples(index=False)
    }
    wanted = {
        (_key(row.source, row.flight_id), int(row.segment_id), int(row.sequence_id)): (
            int(row.sample_order),
            int(row.n_observations),
        )
        for row in sample_manifest.itertuples(index=False)
    }
    sequences: list[tuple[int, np.ndarray]] = []
    for frame in iter_feature_frames(fixes_path, config, allowed_flights=selected):
        key = _key(frame["source"].iloc[0], frame["flight_id"].iloc[0])
        segment_id = int(frame["segment_id"].iloc[0])
        for sequence_id, values in _bounded_feature_blocks(frame, config):
            sample = wanted.get((key, segment_id, sequence_id))
            if sample is None:
                continue
            sample_order, expected_length = sample
            if len(values) != expected_length:
                raise ValueError(
                    "fit sample no longer matches the source feature sequence"
                )
            sequences.append((sample_order, values))
    sequences.sort(key=lambda item: item[0])
    if len(sequences) != len(sample_manifest):
        raise ValueError("one or more persisted fitting sequences were not recovered")
    return [values for _, values in sequences]


def _decode_frame(
    artifact: HMMArtifact, frame: pd.DataFrame
) -> tuple[pd.Series, np.ndarray]:
    """Decode independent valid blocks while preserving interior unavailable gaps."""
    raw = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    probabilities = np.full(
        (len(frame), len(artifact.config.states)), np.nan, dtype=float
    )
    for indexes in valid_feature_block_indexes(frame):
        states, posterior = decode(
            artifact, frame.iloc[indexes][FEATURE_COLUMNS].to_numpy(dtype=float)
        )
        raw.iloc[indexes] = states
        probabilities[indexes] = posterior
    return raw, probabilities


def _raw_labelled_predictions(
    fixes_path: str | Path,
    artifact: HMMArtifact,
    annotations: pd.DataFrame,
    *,
    split: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Decode only manually labelled decision points of one annotation split."""
    raw_parts: list[np.ndarray] = []
    label_parts: list[np.ndarray] = []
    annotation_flights = {
        _key(row.source, row.flight_id)
        for row in annotations.loc[annotations["split"] == split].itertuples(
            index=False
        )
    }
    for frame in iter_feature_frames(
        fixes_path, artifact.config, allowed_flights=annotation_flights
    ):
        labels = labels_for_points(frame, annotations, split=split)
        usable = labels.notna() & valid_feature_mask(frame)
        if not usable.any():
            continue
        decoded, _ = _decode_frame(artifact, frame)
        index = labels.index[usable]
        raw_parts.append(decoded.loc[index].to_numpy(dtype=int))
        label_parts.append(labels.loc[index].to_numpy(dtype=str))
    if not raw_parts:
        raise ValueError(f"no usable {split} manual labels were found in the fix table")
    return np.concatenate(raw_parts), np.concatenate(label_parts)


def train_discipline(
    fixes_path: str | Path,
    model_dir: str | Path,
    config: SegmentationConfig,
    annotations: pd.DataFrame | None = None,
) -> HMMArtifact:
    """Fit an unsupervised HMM and assign its component names.

    Manual ``annotations`` never enter :func:`fit_gaussian_hmm`; when supplied they
    resolve the arbitrary component order after fitting.  Without them, a documented
    mechanics-based mapping permits provisional decoding and annotation preparation,
    but the saved artifact records that it has not yet been manually calibrated.
    """
    manifest = build_split_manifest(fixes_path, config)
    checked = (
        validate_annotation_splits(annotations, manifest)
        if annotations is not None
        else None
    )
    sample_manifest, sequences = collect_fit_sample(fixes_path, manifest, config)
    artifact = fit_gaussian_hmm(sequences, config)
    if checked is None:
        artifact.state_mapping = heuristic_state_mapping(artifact)
        artifact.mapping_method = "provisional-emission-signatures"
    else:
        raw, labels = _raw_labelled_predictions(
            fixes_path, artifact, checked, split="train"
        )
        artifact.state_mapping = semantic_mapping(raw, labels)
        artifact.mapping_method = "manual-train-hungarian"
    destination = Path(model_dir)
    destination.mkdir(parents=True, exist_ok=True)
    manifest.to_parquet(destination / "split_manifest.parquet", index=False)
    sample_manifest.to_parquet(destination / "fit_sample_manifest.parquet", index=False)
    artifact.save(destination)
    return artifact


def _phase_points(frame: pd.DataFrame, artifact: HMMArtifact) -> pd.DataFrame:
    """Decode one feature frame, retaining unclassified feature-edge rows explicitly."""
    out = frame.copy()
    out["phase_raw"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
    out["phase"] = pd.Series("unclassified", index=out.index, dtype="string")
    for state in artifact.config.states:
        out[f"p_{state}"] = np.nan
    valid = valid_feature_mask(out)
    if valid.any():
        raw, probabilities = _decode_frame(artifact, out)
        valid_index = out.index[valid]
        out.loc[valid_index, "phase_raw"] = raw.loc[valid_index].to_numpy(dtype=int)
        out.loc[valid_index, "phase"] = semantic_states(
            artifact, raw.loc[valid_index].to_numpy(dtype=int)
        )
        for component, state in artifact.state_mapping.items():
            out.loc[valid_index, f"p_{state}"] = probabilities[valid, component]
    return out[PHASE_POINT_COLUMNS]


def segment_flight(fixes: pd.DataFrame, artifact: HMMArtifact) -> pd.DataFrame:
    """Decode one already-preprocessed flight without consulting the full archive.

    This is the interactive counterpart of :func:`apply_discipline`: it applies the
    same feature construction, quality masks, independent preprocessing-segment
    boundaries and Viterbi decoder to the flight currently held in memory.  It is
    useful to the trajectory viewer, where scanning a multi-gigabyte point table for
    every click would be wasteful.

    Args:
        fixes: The retained ``FlightResult.fixes`` rows for exactly one flight.
        artifact: The fitted discipline-specific model.

    Returns:
        The standard :data:`PHASE_POINT_COLUMNS` table on the decision grid.  An
        ineligible flight returns the typed empty point table.
    """
    if fixes.empty:
        return _empty_phase_points()
    identities = fixes[["source", "flight_id"]].drop_duplicates()
    if len(identities) != 1:
        raise ValueError("interactive segmentation requires exactly one flight")
    decoded: list[pd.DataFrame] = []
    for _, segment in fixes.groupby("segment_id", sort=False):
        frame = build_feature_frame(segment, artifact.config)
        if not frame.empty:
            decoded.append(_phase_points(frame, artifact))
    if not decoded:
        return _empty_phase_points()
    return pd.concat(decoded, ignore_index=True)[PHASE_POINT_COLUMNS]


def _phase_runs(points: pd.DataFrame, config: SegmentationConfig) -> pd.DataFrame:
    """Collapse a decoded segment into state runs and record boundary censoring."""
    available = (points["phase"] != "unclassified").to_numpy(dtype=bool)
    positions = np.flatnonzero(available)
    if positions.size == 0:
        return pd.DataFrame(columns=PHASE_SEGMENT_COLUMNS)
    rows: list[dict[str, object]] = []
    block_starts = np.r_[0, np.flatnonzero(np.diff(positions) > 1) + 1]
    block_ends = np.r_[block_starts[1:], len(positions)]
    for block_start, block_end in zip(block_starts, block_ends, strict=True):
        block = points.iloc[positions[block_start:block_end]].reset_index(drop=True)
        starts = np.r_[
            True,
            block["phase"].to_numpy()[1:] != block["phase"].to_numpy()[:-1],
        ]
        run_ids = np.cumsum(starts) - 1
        for _, run in block.groupby(run_ids, sort=False):
            phase = str(run["phase"].iloc[0])
            first_t, last_t = float(run["t"].iloc[0]), float(run["t"].iloc[-1])
            rows.append(
                {
                    "source": run["source"].iloc[0],
                    "flight_id": run["flight_id"].iloc[0],
                    "segment_id": run["segment_id"].iloc[0],
                    "phase": phase,
                    "t_start": first_t - config.decision_step_s / 2.0,
                    "t_end": last_t + config.decision_step_s / 2.0,
                    "duration_s": len(run) * config.decision_step_s,
                    "n_points": len(run),
                    "mean_posterior": float(run[f"p_{phase}"].mean()),
                    "left_censored": bool(run.index[0] == 0),
                    "right_censored": bool(run.index[-1] == len(block) - 1),
                }
            )
    return pd.DataFrame(rows, columns=PHASE_SEGMENT_COLUMNS)


def _append_parquet(
    writer: Any | None, path: Path, frame: pd.DataFrame, schema: Any | None
) -> tuple[Any, Any]:
    """Append a non-empty Pandas frame to a schema-stable Parquet writer."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(frame, preserve_index=False)
    if writer is None:
        schema = table.schema
        writer = pq.ParquetWriter(path, schema, compression="zstd")
    writer.write_table(table.cast(schema))
    return writer, schema


def _empty_phase_segments() -> pd.DataFrame:
    """Return a typed empty run table when no classifiable run was observed."""
    dtypes = {
        "source": "string",
        "flight_id": "string",
        "segment_id": "int64",
        "phase": "string",
        "t_start": "float64",
        "t_end": "float64",
        "duration_s": "float64",
        "n_points": "int64",
        "mean_posterior": "float64",
        "left_censored": "bool",
        "right_censored": "bool",
    }
    return pd.DataFrame(
        {column: pd.Series(dtype=dtypes[column]) for column in PHASE_SEGMENT_COLUMNS}
    )


def _empty_phase_points() -> pd.DataFrame:
    """Return a typed empty decision-point table for an entirely ineligible archive."""
    dtypes = {
        "source": "string",
        "flight_id": "string",
        "segment_id": "int64",
        "t": "float64",
        "E": "float64",
        "N": "float64",
        "z": "float64",
        "feature_edge": "bool",
        "quality_masked": "bool",
        **dict.fromkeys(FEATURE_COLUMNS, "float64"),
        "phase_raw": "Int64",
        "phase": "string",
        "p_transition": "float64",
        "p_search": "float64",
        "p_climb": "float64",
    }
    return pd.DataFrame(
        {column: pd.Series(dtype=dtypes[column]) for column in PHASE_POINT_COLUMNS}
    )


def _empty_phase_coverage() -> pd.DataFrame:
    """Return a typed segment-eligibility audit table."""
    dtypes = {
        "source": "string",
        "flight_id": "string",
        "segment_id": "int64",
        "t_start": "float64",
        "t_end": "float64",
        "n_native_fixes": "int64",
        "native_cadence_s": "float64",
        "n_decision_points": "int64",
        "n_classifiable_points": "int64",
        "status": "string",
    }
    return pd.DataFrame(
        {column: pd.Series(dtype=dtypes[column]) for column in PHASE_COVERAGE_COLUMNS}
    )


def _decode_flight(
    flight: pd.DataFrame, artifact: HMMArtifact
) -> list[tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]]:
    """Build coverage, points, and runs for one thread-independent flight."""
    decoded = []
    for _, segment in flight.groupby("segment_id", sort=False):
        frame = build_feature_frame(segment, artifact.config)
        cadence = native_cadence_s(segment)
        n_classifiable = int(valid_feature_mask(frame).sum()) if not frame.empty else 0
        coverage = pd.DataFrame(
            [
                {
                    "source": segment["source"].iloc[0],
                    "flight_id": segment["flight_id"].iloc[0],
                    "segment_id": int(segment["segment_id"].iloc[0]),
                    "t_start": float(segment["t"].min()),
                    "t_end": float(segment["t"].max()),
                    "n_native_fixes": len(segment),
                    "native_cadence_s": cadence,
                    "n_decision_points": len(frame),
                    "n_classifiable_points": n_classifiable,
                    "status": (
                        "skipped_native_cadence"
                        if frame.empty
                        else ("decoded" if n_classifiable else "unclassifiable_window")
                    ),
                }
            ],
            columns=PHASE_COVERAGE_COLUMNS,
        )
        if frame.empty:
            decoded.append((coverage, None, None))
            continue
        points = _phase_points(frame, artifact)
        runs = _phase_runs(points, artifact.config)
        decoded.append((coverage, points, None if runs.empty else runs))
    return decoded


def _flight_batches(
    flights: Iterator[pd.DataFrame], size: int
) -> Iterator[list[pd.DataFrame]]:
    """Yield bounded batches without submitting an entire archive to an executor."""
    while batch := list(islice(flights, size)):
        yield batch


def _decoded_flights(
    flights: Iterator[pd.DataFrame], artifact: HMMArtifact, workers: int
) -> Iterator[list[tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]]]:
    """Decode flights serially or in bounded process batches, preserving order."""
    if workers == 1:
        for flight in flights:
            yield _decode_flight(flight, artifact)
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for batch in _flight_batches(flights, 4 * workers):
            yield from executor.map(
                _decode_flight, batch, [artifact] * len(batch), chunksize=1
            )


def apply_discipline(
    fixes_path: str | Path, model_dir: str | Path, output_dir: str | Path
) -> tuple[Path, Path]:
    """Decode all eligible segments and write separate point and run Parquet tables."""
    artifact = HMMArtifact.load(model_dir)
    # One artifact is shared read-only by the flight workers.  Log-space inference is
    # robust to extreme held-out emissions and avoids per-call implementation toggles.
    artifact.model.implementation = "log"
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    points_path = destination / "phase_points.parquet"
    runs_path = destination / "phase_segments.parquet"
    coverage_path = destination / "phase_coverage.parquet"
    point_writer: Any | None = None
    run_writer: Any | None = None
    coverage_writer: Any | None = None
    point_schema: Any | None = None
    run_schema: Any | None = None
    coverage_schema: Any | None = None
    point_buffer: list[pd.DataFrame] = []
    run_buffer: list[pd.DataFrame] = []
    coverage_buffer: list[pd.DataFrame] = []
    point_rows = run_rows = 0
    coverage_rows = 0
    flights = stream_flights(fixes_path, _FEATURE_INPUT_COLUMNS)
    workers = max(1, min(artifact.config.n_jobs, 8))
    for flight_result in _decoded_flights(flights, artifact, workers):
        for coverage, points, runs in flight_result:
            coverage_buffer.append(coverage)
            coverage_rows += 1
            if coverage_rows >= _PARQUET_BATCH_ROWS:
                coverage_writer, coverage_schema = _append_parquet(
                    coverage_writer,
                    coverage_path,
                    pd.concat(coverage_buffer, ignore_index=True),
                    coverage_schema,
                )
                coverage_buffer = []
                coverage_rows = 0
            if points is None:
                continue
            point_buffer.append(points)
            point_rows += len(points)
            if point_rows >= _PARQUET_BATCH_ROWS:
                point_writer, point_schema = _append_parquet(
                    point_writer,
                    points_path,
                    pd.concat(point_buffer, ignore_index=True),
                    point_schema,
                )
                point_buffer = []
                point_rows = 0
            if runs is not None:
                run_buffer.append(runs)
                run_rows += len(runs)
                if run_rows >= _PARQUET_BATCH_ROWS:
                    run_writer, run_schema = _append_parquet(
                        run_writer,
                        runs_path,
                        pd.concat(run_buffer, ignore_index=True),
                        run_schema,
                    )
                    run_buffer = []
                    run_rows = 0
    if point_buffer:
        point_writer, point_schema = _append_parquet(
            point_writer,
            points_path,
            pd.concat(point_buffer, ignore_index=True),
            point_schema,
        )
    if run_buffer:
        run_writer, run_schema = _append_parquet(
            run_writer,
            runs_path,
            pd.concat(run_buffer, ignore_index=True),
            run_schema,
        )
    if coverage_buffer:
        coverage_writer, coverage_schema = _append_parquet(
            coverage_writer,
            coverage_path,
            pd.concat(coverage_buffer, ignore_index=True),
            coverage_schema,
        )
    if point_writer is None:
        _empty_phase_points().to_parquet(points_path, index=False)
    else:
        point_writer.close()
    if run_writer is None:
        _empty_phase_segments().to_parquet(runs_path, index=False)
    else:
        run_writer.close()
    if coverage_writer is None:
        _empty_phase_coverage().to_parquet(coverage_path, index=False)
    else:
        coverage_writer.close()
    return points_path, runs_path


def _mapping_from_decoded_points(
    points_path: Path,
    annotations: pd.DataFrame,
    manifest: pd.DataFrame,
) -> dict[int, str]:
    """Resolve component names from train labels without rereading raw trajectories."""
    checked = validate_annotation_splits(annotations, manifest)
    train = checked.loc[checked["split"] == "train"]
    if train.empty:
        raise ValueError("manual calibration requires train annotations")
    flight_ids = train["flight_id"].astype(str).unique().tolist()
    points = pd.read_parquet(
        points_path,
        columns=["source", "flight_id", "segment_id", "t", "phase_raw"],
        filters=[("flight_id", "in", flight_ids)],
    )
    labels = labels_for_points(points, checked, split="train")
    usable = labels.notna() & points["phase_raw"].notna()
    if not usable.any():
        raise ValueError("no classifiable train labels overlap decoded phase points")
    return semantic_mapping(
        points.loc[usable, "phase_raw"].to_numpy(dtype=int),
        labels.loc[usable].to_numpy(dtype=str),
    )


def _remap_points(
    points: pd.DataFrame,
    old_mapping: dict[int, str],
    new_mapping: dict[int, str],
) -> pd.DataFrame:
    """Apply a new component permutation without recomputing HMM inference."""
    out = points.copy()
    old_probabilities = {
        component: out[f"p_{state}"].to_numpy(copy=True)
        for component, state in old_mapping.items()
    }
    inverse_new = {state: component for component, state in new_mapping.items()}
    for state in STATES:
        out[f"p_{state}"] = old_probabilities[inverse_new[state]]
    classified = out["phase_raw"].notna()
    out.loc[~classified, "phase"] = "unclassified"
    out.loc[classified, "phase"] = [
        new_mapping[int(component)]
        for component in out.loc[classified, "phase_raw"].to_numpy(dtype=int)
    ]
    return out[PHASE_POINT_COLUMNS]


def calibrate_discipline(
    output_dir: str | Path, annotations: pd.DataFrame
) -> HMMArtifact:
    """Apply manual state names and atomically relabel existing decoded artifacts."""
    root = Path(output_dir)
    model_dir = root / "model"
    points_path = root / "phase_points.parquet"
    runs_path = root / "phase_segments.parquet"
    artifact = HMMArtifact.load(model_dir)
    manifest = pd.read_parquet(model_dir / "split_manifest.parquet")
    new_mapping = _mapping_from_decoded_points(points_path, annotations, manifest)
    old_mapping = artifact.state_mapping.copy()
    calibrated = replace(artifact, state_mapping=new_mapping)

    temporary_points = root / ".phase_points.calibrating.parquet"
    temporary_runs = root / ".phase_segments.calibrating.parquet"
    temporary_points.unlink(missing_ok=True)
    temporary_runs.unlink(missing_ok=True)
    point_writer: Any | None = None
    run_writer: Any | None = None
    point_schema: Any | None = None
    run_schema: Any | None = None
    point_buffer: list[pd.DataFrame] = []
    run_buffer: list[pd.DataFrame] = []
    point_rows = run_rows = 0
    try:
        for flight in stream_flights(points_path):
            if artifact.config.sequence_prior.weight:
                # Semantic transition preferences change when names are calibrated.
                # Re-decode saved features, preserving segment and quality boundaries.
                remapped = pd.concat(
                    [
                        _phase_points(segment.reset_index(drop=True), calibrated)
                        for _, segment in flight.groupby("segment_id", sort=False)
                    ],
                    ignore_index=True,
                )
            else:
                remapped = _remap_points(flight, old_mapping, new_mapping)
            point_buffer.append(remapped)
            point_rows += len(remapped)
            for _, segment in remapped.groupby("segment_id", sort=False):
                runs = _phase_runs(segment, artifact.config)
                if not runs.empty:
                    run_buffer.append(runs)
                    run_rows += len(runs)
            if point_rows >= _PARQUET_BATCH_ROWS:
                point_writer, point_schema = _append_parquet(
                    point_writer,
                    temporary_points,
                    pd.concat(point_buffer, ignore_index=True),
                    point_schema,
                )
                point_buffer = []
                point_rows = 0
            if run_rows >= _PARQUET_BATCH_ROWS:
                run_writer, run_schema = _append_parquet(
                    run_writer,
                    temporary_runs,
                    pd.concat(run_buffer, ignore_index=True),
                    run_schema,
                )
                run_buffer = []
                run_rows = 0
        if point_buffer:
            point_writer, point_schema = _append_parquet(
                point_writer,
                temporary_points,
                pd.concat(point_buffer, ignore_index=True),
                point_schema,
            )
        if run_buffer:
            run_writer, run_schema = _append_parquet(
                run_writer,
                temporary_runs,
                pd.concat(run_buffer, ignore_index=True),
                run_schema,
            )
    finally:
        if point_writer is not None:
            point_writer.close()
        if run_writer is not None:
            run_writer.close()
    if point_writer is None or run_writer is None:
        raise ValueError("calibration produced an empty phase artifact")
    temporary_points.replace(points_path)
    temporary_runs.replace(runs_path)
    artifact.state_mapping = new_mapping
    artifact.mapping_method = "manual-train-hungarian"
    artifact.save(model_dir)
    return artifact


def evaluate_discipline(
    points_path: str | Path,
    annotations: pd.DataFrame,
    *,
    split: str,
    config: SegmentationConfig,
) -> tuple[ClassificationMetrics, tuple[float, float]]:
    """Evaluate a decoded table against one untouched manual-label split."""
    stored_config = HMMArtifact.load(Path(points_path).parent / "model").config
    if config != stored_config:
        raise ValueError(
            "evaluation configuration differs from that stored with the HMM"
        )
    truth, prediction, flights = labelled_phase_predictions(
        points_path, annotations, split=split
    )
    metrics = classification_metrics(truth, prediction, flights)
    interval = bootstrap_macro_f1(
        truth,
        prediction,
        flights,
        seed=config.random_seed,
        replicates=config.bootstrap_replicates,
    )
    return metrics, interval


def _manifest_for_phase_points(points_path: str | Path) -> pd.DataFrame:
    """Load the split manifest paired with a decoded phase-points table."""
    path = Path(points_path)
    manifest_path = path.parent / "model" / "split_manifest.parquet"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"{manifest_path} is required to evaluate held-out phase annotations"
        )
    return pd.read_parquet(manifest_path)


def labelled_phase_predictions(
    points_path: str | Path,
    annotations: pd.DataFrame,
    *,
    split: str,
    manifest: pd.DataFrame | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Stream labelled truth/prediction pairs for metrics or a confusion matrix."""
    import pyarrow.parquet as pq

    checked = validate_annotation_splits(
        annotations,
        _manifest_for_phase_points(points_path) if manifest is None else manifest,
    )
    truth_parts: list[np.ndarray] = []
    prediction_parts: list[np.ndarray] = []
    flight_parts: list[np.ndarray] = []
    parquet = pq.ParquetFile(points_path)
    columns = [
        "source",
        "flight_id",
        "segment_id",
        "t",
        "feature_edge",
        "quality_masked",
        "phase",
    ]
    for row_group in range(parquet.metadata.num_row_groups):
        points = parquet.read_row_group(row_group, columns=columns).to_pandas()
        truth = labels_for_points(points, checked, split=split)
        usable = truth.notna() & valid_feature_mask(points)
        if usable.any():
            truth_parts.append(truth.loc[usable].to_numpy(dtype=str))
            prediction_parts.append(points.loc[usable, "phase"].to_numpy(dtype=str))
            flight_parts.append(points.loc[usable, "flight_id"].to_numpy())
    if not truth_parts:
        raise ValueError(
            f"no usable {split} annotations intersect decoded phase points"
        )
    return (
        np.concatenate(truth_parts),
        np.concatenate(prediction_parts),
        np.concatenate(flight_parts),
    )


def write_metrics(
    path: str | Path, metrics: ClassificationMetrics, interval: tuple[float, float]
) -> None:
    """Write validation/test metrics in a portable, inspectable JSON record."""
    payload = {
        "accuracy": metrics.accuracy,
        "macro_f1": metrics.macro_f1,
        "macro_f1_95pct_ci": list(interval),
        "n_points": metrics.n_points,
        "n_flights": metrics.n_flights,
        "per_state": metrics.per_state,
    }
    Path(path).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
