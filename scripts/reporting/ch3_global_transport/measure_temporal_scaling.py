#!/usr/bin/env python3
"""Measure a frozen signed/two-interval scaling protocol on verified coordinates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"

import numpy as np
import pandas as pd

from soaring.analysis.observables.archive_diagnostics import DiskFrames
from soaring.analysis.observables.segment_support import increment_starts
from soaring.analysis.observables.temporal_scaling import (
    cdf_features,
    fit_histogram_quantiles,
    magnitude_histograms,
    projection_directions,
    simultaneous_contrasts,
    training_day,
    two_increments,
)
from soaring.reporting import DISCIPLINES

ROOT = Path(__file__).resolve().parents[3]
FRAMES = None


def digest(path):
    """Hash complete bytes, including the coordinate store."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    """Write a small reviewable measurement record."""
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def initialise(directory):
    """Map the same read-only coordinate file in each bounded worker."""
    global FRAMES
    FRAMES = DiskFrames(directory)


def chunk_measure(task):
    """Aggregate a bounded flight batch; never materialise archive increments."""
    indexes, day_ids, lags, thresholds, fit = task
    directions, _ = projection_directions()
    edges = np.geomspace(1e-6, 1e7, 8193)
    total = np.zeros((len(lags), 3, len(edges) + 1)) if fit is None else {}
    for index, day in zip(indexes, day_ids, strict=True):
        row, xy = FRAMES[int(index)]
        curves = []
        for li, lag in enumerate(lags):
            values = two_increments(row, xy, lag // 10, max(lags) // 10)
            if fit is None:
                total[li] += magnitude_histograms(values, edges)
            else:
                scale = fit["reference_radius_m"] * (lag / lags[0]) ** fit["common_h"]
                curves.append(cdf_features(values / scale, directions, thresholds))
        if fit is not None:
            if int(day) not in total:
                total[int(day)] = np.zeros(
                    (len(lags), len(directions), len(thresholds))
                )
            total[int(day)] += curves
    return total


def collect(pool, indexes, days, lags, thresholds, fit):
    """Bound submitted work and accumulated results by twice the worker count."""
    chunks = iter(
        (indexes[k : k + 256], days[k : k + 256], lags, thresholds, fit)
        for k in range(0, len(indexes), 256)
    )
    pending = deque()
    for _ in range(2 * pool._max_workers):
        task = next(chunks, None)
        if task is not None:
            pending.append(pool.submit(chunk_measure, task))
    complete, total = 0, None
    started = time.monotonic()
    while pending:
        value = pending.popleft().result()
        if fit is None:
            total = value if total is None else total + value
        else:
            if total is None:
                total = np.zeros((int(days.max()) + 1, len(lags), 16, len(thresholds)))
            for day, curves in value.items():
                total[day] += curves
        complete += 256
        if complete % 10240 == 0:
            print(
                f"  {'fit' if fit is None else 'validate'}: "
                f"{min(complete, len(indexes))}/{len(indexes)} flights, "
                f"{time.monotonic() - started:.0f}s",
                flush=True,
            )
        task = next(chunks, None)
        if task is not None:
            pending.append(pool.submit(chunk_measure, task))
    return total


def main():
    """Save source identities before results and complete immutable reports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--coordinate-manifest",
        type=Path,
        default=ROOT / "revisions/regional-pca-lags-2026-09-12/numerical-update.json",
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "revisions/temporal-self-similarity-2026-09-13/protocol.json",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if (args.out / "report.json").exists():
        raise FileExistsError("Completed reports are immutable")
    protocol = json.loads(args.protocol.read_text())
    sources = [
        Path(__file__),
        ROOT / "src/soaring/analysis/observables/temporal_scaling.py",
        ROOT / "src/soaring/analysis/observables/segment_support.py",
        ROOT / "src/soaring/analysis/observables/archive_diagnostics.py",
        args.protocol,
    ]
    parent_path = args.coordinate_manifest
    parent = json.loads(parent_path.read_text())
    assert parent["status"] == "complete"
    contract = {
        "sources": {str(p.relative_to(ROOT)): digest(p) for p in sources},
        "coordinate_manifest_sha256": digest(parent_path),
        "protocol": protocol,
    }
    contract_path = args.out / "contract.json"
    if contract_path.exists():
        if json.loads(contract_path.read_text()) != contract:
            raise ValueError(
                "Resume requires identical measurement sources and protocol"
            )
    else:
        write_json(contract_path, contract)
    inputs, results = {}, {}
    started = time.monotonic()
    directions, names = projection_directions()
    # E1/N1; signed spatial joint projections; all directions involving interval 2.
    groups = {
        "east": [0],
        "north": [1],
        "spatial": [0, 1, 4, 5],
        "temporal": [i for i in range(16) if i not in (0, 1, 4, 5)],
        "all": list(range(16)),
    }
    for discipline, glider in DISCIPLINES.items():
        candidates = [
            ROOT / p
            for p in parent["coordinate_inputs"]
            if p.endswith(f"ch3-full-{glider.slug}/flights.json")
        ]
        assert len(candidates) == 1
        directory = candidates[0].parent.resolve()
        for name in ("flights.json", "positions.bin"):
            path = directory / name
            key = next(
                p for p in parent["coordinate_inputs"] if (ROOT / p).resolve() == path
            )
            actual = digest(path)
            assert actual == parent["coordinate_inputs"][key]["sha256"], path
            inputs[str(path)] = {"sha256": actual, "bytes": path.stat().st_size}
        catalog_path = Path(glider.catalog_path())
        inputs[str(catalog_path)] = {
            "sha256": digest(catalog_path),
            "bytes": catalog_path.stat().st_size,
        }
        catalog = pd.read_csv(
            catalog_path, usecols=["flight_id", "date"], dtype="string"
        ).set_index("flight_id")
        if catalog.index.has_duplicates:
            raise ValueError("Duplicate catalogue identifiers")
        frames = DiskFrames(directory)
        dates = (
            pd.to_datetime(
                catalog.reindex([str(r["flight_id"]) for r in frames.rows]).date,
                format="%Y-%m-%d",
                errors="coerce",
            )
            .dt.strftime("%Y-%m-%d")
            .to_numpy()
        )
        valid = pd.notna(dates)
        train = np.array(
            [
                training_day(d) if ok else False
                for d, ok in zip(dates, valid, strict=True)
            ]
        )
        output = args.out / glider.slug
        output.mkdir(exist_ok=True)
        results[discipline] = {}
        with ProcessPoolExecutor(
            max_workers=args.workers, initializer=initialise, initargs=(directory,)
        ) as pool:
            for regime, lags in protocol["regimes"].items():
                prefix = output / regime
                completed = prefix.with_suffix(".json")
                if completed.exists():
                    result = json.loads(completed.read_text())
                    assert digest(prefix.with_suffix(".npz")) == result["arrays_sha256"]
                    results[discipline][regime] = result
                    continue
                counts = np.array(
                    [
                        len(
                            increment_starts(
                                r, r["length"], max(lags) // 10, order=2, stride=1
                            )
                        )
                        for r in frames.rows
                    ]
                )
                eligible = counts > 0
                train_indexes = np.flatnonzero(eligible & valid & train)
                test_indexes = np.flatnonzero(eligible & valid & ~train)
                day_names, day_ids = np.unique(dates[test_indexes], return_inverse=True)
                print(
                    f"{discipline} {regime}: {len(train_indexes)} training / "
                    f"{len(test_indexes)} validation flights; "
                    f"{len(day_names)} validation days",
                    flush=True,
                )
                hist = collect(
                    pool,
                    train_indexes,
                    np.zeros(len(train_indexes), dtype=int),
                    lags,
                    protocol["cdf_thresholds"],
                    None,
                )
                fit = fit_histogram_quantiles(
                    hist, np.geomspace(1e-6, 1e7, 8193), lags, [0.25, 0.5, 0.75, 0.9]
                )
                day_sums = collect(
                    pool, test_indexes, day_ids, lags, protocol["cdf_thresholds"], fit
                )
                day_counts = np.bincount(day_ids)
                mean, contrasts, band, errors = simultaneous_contrasts(
                    day_sums,
                    day_counts,
                    resamples=protocol["bootstrap_resamples"],
                    seed=protocol["seed"],
                )
                diagnostics = {}
                for group, indexes in groups.items():
                    distance = float(np.abs(contrasts[:, indexes]).max())
                    upper = min(1.0, distance + band)
                    diagnostics[group] = {
                        "distance": distance,
                        "lower_95": max(0.0, distance - band),
                        "upper_95": upper,
                        "supported_tolerances": [
                            t for t in protocol["tolerances"] if upper < t
                        ],
                    }
                np.savez_compressed(
                    prefix.with_suffix(".npz"),
                    training_histograms=hist,
                    day_sums=day_sums,
                    day_counts=day_counts,
                    validation_dates=day_names.astype(str),
                    validation_flight_indexes=test_indexes,
                    training_flight_indexes=train_indexes,
                    common_origin_counts=counts,
                    mean_cdfs=mean,
                    contrasts=contrasts,
                    bootstrap_uniform_errors=errors,
                )
                result = {
                    "lags_s": lags,
                    "n_eligible_flights": int(eligible.sum()),
                    "invalid_date_flights": int((eligible & ~valid).sum()),
                    "n_training_flights": len(train_indexes),
                    "n_validation_flights": len(test_indexes),
                    "n_training_days": len(np.unique(dates[train_indexes])),
                    "n_validation_days": len(day_names),
                    "n_training_origins": int(counts[train_indexes].sum()),
                    "n_validation_origins": int(counts[test_indexes].sum()),
                    "fit": fit,
                    "simultaneous_band_radius": band,
                    "diagnostics": diagnostics,
                    "arrays_sha256": digest(prefix.with_suffix(".npz")),
                }
                write_json(completed, result)
                results[discipline][regime] = result
                print(
                    f"  H={fit['common_h']:.4f}, simultaneous radius={band:.4f}, "
                    f"all projections={diagnostics['all']}",
                    flush=True,
                )
    assert contract["sources"] == {str(p.relative_to(ROOT)): digest(p) for p in sources}
    report = {
        "status": "complete",
        "completed_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": time.monotonic() - started,
        "contract_sha256": digest(contract_path),
        "cleaning": parent["cleaning"],
        "inputs": inputs,
        "protocol": protocol,
        "projection_directions": directions.tolist(),
        "projection_names": names,
        "groups": groups,
        "results": results,
    }
    write_json(args.out / "report.json", report)


if __name__ == "__main__":
    main()
