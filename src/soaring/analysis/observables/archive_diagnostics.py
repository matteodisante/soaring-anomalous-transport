"""Full-archive diagnostics with disk-backed coordinates and bounded worker queues.

Every eligible segment is retained, including flights crossing Parquet row groups.
Increment origins never cross segment boundaries. Flight means pool their eligible
origins before flights receive equal weight. Pooled increment laws retain their
explicit origin weighting. Native cadences above the common 10 s grid are excluded.
"""

from __future__ import annotations

import json
import os
import pickle
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from ..derived import stream_flights
from .persistence import velocity_autocorrelation
from .segment_support import increment_starts, segment_ranges


class DiskFrames:
    """Reusable flight sequence whose coordinate arrays stay mapped on disk."""

    def __init__(self, directory):
        """Open a completed coordinate store and its flight index."""
        self.directory = Path(directory)
        self.rows = json.loads((self.directory / "flights.json").read_text())
        path = self.directory / "positions.bin"
        self.positions = np.memmap(path, dtype="float64", mode="r").reshape(-1, 2)

    def __len__(self):
        """Count complete eligible flights."""
        return len(self.rows)

    def __getitem__(self, index):
        """Read one flight without copying the complete archive."""
        row = self.rows[index]
        return row, self.positions[row["offset"] : row["offset"] + row["length"]]

    def __iter__(self):
        """Visit the recorded flight order deterministically."""
        for i in range(len(self)):
            yield self[i]


def collect_archive(glider, directory, regions, classify, signature):
    """Stream all eligible flights into one compact coordinate store.

    Cadence and minimum support are explicit eligibility criteria, not sampling
    caps. All admitted segments contribute; no synthetic adjacency joins them.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".incomplete").write_text("collecting full archive\n")
    derived = glider.derived_dir()
    path = derived / "fixes.parquet"
    meta = pd.read_parquet(
        derived / "flights_meta.parquet", columns=["flight_id", "lat0", "lon0"]
    ).set_index("flight_id")
    meta.index = meta.index.astype(str)
    catalog = pd.read_csv(
        glider.catalog_path(),
        usecols=["flight_id", "flight_type"],
        dtype={"flight_id": str},
    ).set_index("flight_id")
    if meta.index.has_duplicates or catalog.index.has_duplicates:
        raise ValueError("Duplicate flight metadata")
    rows, offset = [], 0
    excluded = {"cadence_above_10s": 0, "insufficient_support": 0}
    seen = 0
    with (directory / "positions.bin").open("wb") as output:
        for flight in stream_flights(path, ["segment_id", "t", "E", "N"]):
            seen += 1
            flight_id = str(flight.flight_id.iloc[0])
            pieces, ranges, ids, starts, durations = [], [], [], [], []
            size, path_length = 0, 0.0
            native = []
            for sid, segment in flight.groupby("segment_id", sort=False):
                t = segment.t.to_numpy(dtype=float)
                if len(t) < 2 or not np.all(np.diff(t) > 0):
                    raise ValueError("Non-increasing or singleton retained segment")
                dt = float(np.median(np.diff(t)))
                if dt > 10:
                    excluded["cadence_above_10s"] += 1
                    continue
                grid = np.arange(t[0], t[-1] + 1e-7, 10.0)
                if len(grid) < 2:
                    excluded["insufficient_support"] += 1
                    continue
                xy = np.column_stack(
                    [np.interp(grid, t, segment[c]) for c in ("E", "N")]
                )
                if not np.isfinite(xy).all():
                    raise ValueError("Non-finite retained coordinates")
                ranges.append([size, size + len(xy)])
                size += len(xy)
                pieces.append(xy)
                ids.append(int(sid))
                starts.append(float(grid[0]))
                durations.append(float(grid[-1] - grid[0]))
                native.append(dt)
                path_length += float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum())
            if not pieces:
                continue
            xy = np.concatenate(pieces)
            xy -= xy[0]
            lat, lon = meta.loc[flight_id, ["lat0", "lon0"]].to_numpy(dtype=float)
            region = next(
                (
                    name
                    for name, (w, e, s, n) in regions.items()
                    if w <= lon <= e and s <= lat <= n
                ),
                "other",
            )
            task = (
                str(catalog.loc[flight_id, "flight_type"])
                if flight_id in catalog.index
                else "unknown"
            )
            category = classify(task)
            row = {
                "flight_id": flight_id,
                "segment_id": ids[int(np.argmax(durations))],
                "segment_ids": ids,
                "segments": ranges,
                "segment_start_s": starts,
                "duration_s": max(durations),
                "retained_duration_s": sum(durations),
                "native_dt_s": max(native),
                "region": region,
                "task": task,
                "closed": category == "closed",
                "task_known": category != "unknown",
                "closure_ratio": float(np.linalg.norm(xy[-1]) / path_length)
                if path_length
                else 0.0,
                "offset": offset,
                "length": len(xy),
            }
            output.write(xy.astype("float64", copy=False).tobytes())
            offset += len(xy)
            rows.append(row)
            if seen % 10000 == 0:
                print(
                    f"{glider.slug}: {seen} flights read, {len(rows)} eligible",
                    flush=True,
                )
    if not rows:
        raise ValueError("No eligible flights in the full archive")
    (directory / "flights.json").write_text(json.dumps(rows))
    provenance = {
        "scope": "all eligible flights and segments",
        "sampling": False,
        "native_max_s": 10,
        "grid_s": 10,
        "archive_flights": seen,
        "eligible_flights": len(rows),
        "eligible_segments": sum(len(r["segments"]) for r in rows),
        "excluded_segments": excluded,
        "flights": rows,
        "inputs": {
            "fixes": signature(path),
            "metadata": signature(derived / "flights_meta.parquet"),
            "tasks": signature(Path(glider.catalog_path())),
        },
    }
    return DiskFrames(directory), provenance


def _flight_measure(task):
    """Compute one flight's increments and bounded sufficient statistics."""
    row, position, lags, scales = task
    variations = np.full((2, len(lags)), np.nan)
    vectors = []
    for j, tau in enumerate(lags):
        lag = int(tau // 10)
        starts = increment_starts(row, len(position), lag)
        xy = position[starts + lag] - position[starts]
        vectors.append(xy)
        if len(starts):
            variations[0, j] = np.mean(np.einsum("ij,ij->i", xy, xy))
        starts = increment_starts(row, len(position), lag, order=2)
        if len(starts):
            second = (
                position[starts + 2 * lag]
                - 2 * position[starts + lag]
                + position[starts]
            )
            variations[1, j] = np.mean(np.einsum("ij,ij->i", second, second))
    coarse = {}
    for scale in scales:
        size = 10000 // scale + 1
        total, count = np.zeros(size), np.zeros(size, dtype=int)
        for start, stop in segment_ranges(row, len(position)):
            velocity = np.diff(position[start : stop : scale // 10], axis=0) / scale
            index, corr = velocity_autocorrelation(
                velocity, max_lag=min(len(velocity) // 4, size - 1)
            )
            good = np.isfinite(corr)
            total[index[good]] += corr[good]
            count[index[good]] += 1
        coarse[scale] = np.divide(
            total, count, out=np.full(size, np.nan), where=count > 0
        )
    return variations, vectors, coarse


def _batch_measure(batch):
    """Amortise worker scheduling without accumulating unbounded futures."""
    return [_flight_measure(task) for task in batch]


def _ordered_results(tasks, workers, batch_size=16):
    """Yield in source order with at most two batches queued per worker."""
    from collections import deque
    from itertools import islice

    if workers == 1:
        for task in tasks:
            yield _flight_measure(task)
        return
    iterator = iter(tasks)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending = deque()
        for _ in range(2 * workers):
            batch = list(islice(iterator, batch_size))
            if batch:
                pending.append(pool.submit(_batch_measure, batch))
        while pending:
            yield from pending.popleft().result()
            batch = list(islice(iterator, batch_size))
            if batch:
                pending.append(pool.submit(_batch_measure, batch))


def measure_archive(frames, directory, lags, scales, q, probabilities, workers=None):
    """Measure all flights while spilling increment pools by lag to disk."""
    from contextlib import ExitStack

    directory = Path(directory)
    (directory / ".incomplete").write_text("measuring full archive\n")
    workers = (
        max(1, int(os.environ.get("SOARING_MAX_WORKERS", str(os.cpu_count() or 1))))
        if workers is None
        else workers
    )
    if workers < 1:
        raise ValueError("workers must be positive")
    variations = np.empty((len(frames), 2, len(lags)))
    coarse_sum = {s: np.zeros(10000 // s + 1) for s in scales}
    coarse_count = {s: np.zeros(10000 // s + 1, dtype=int) for s in scales}
    counts = np.zeros(len(lags), dtype=np.int64)
    tasks = ((row, np.asarray(pos), lags, scales) for row, pos in frames)
    with ExitStack() as stack:
        vector_files = [
            stack.enter_context(
                (directory / f"vectors-{j}.bin").open("wb", buffering=1024 * 1024)
            )
            for j in range(len(lags))
        ]
        owner_files = [
            stack.enter_context(
                (directory / f"owners-{j}.bin").open("wb", buffering=1024 * 1024)
            )
            for j in range(len(lags))
        ]
        for i, (variation, vectors, coarse) in enumerate(
            _ordered_results(tasks, workers)
        ):
            variations[i] = variation
            for j, xy in enumerate(vectors):
                vector_files[j].write(xy.astype("float64", copy=False).tobytes())
                owner_files[j].write(np.full(len(xy), i, dtype="int32").tobytes())
                counts[j] += len(xy)
            for scale, corr in coarse.items():
                good = np.isfinite(corr)
                coarse_sum[scale][good] += corr[good]
                coarse_count[scale][good] += 1
            if (i + 1) % 10000 == 0:
                print(
                    f"full diagnostics: {i + 1}/{len(frames)} flights "
                    f"measured ({workers} workers)",
                    flush=True,
                )
    vectors = [
        np.memmap(
            directory / f"vectors-{j}.bin", mode="r", dtype="float64", shape=(int(n), 2)
        )
        if n
        else np.empty((0, 2))
        for j, n in enumerate(counts)
    ]
    owners = [
        np.memmap(
            directory / f"owners-{j}.bin", mode="r", dtype="int32", shape=(int(n),)
        )
        if n
        else np.empty(0, dtype="int32")
        for j, n in enumerate(counts)
    ]
    moments = np.full((len(lags), len(q)), np.nan)
    quantiles = np.full((len(lags), 3, len(probabilities)), np.nan)
    kurtosis = np.full(len(lags), np.nan)
    for j, xy in enumerate(vectors):
        if len(xy) < 30:
            continue
        sums = np.zeros(len(q))
        for start in range(0, len(xy), 100000):
            radial = np.linalg.norm(xy[start : start + 100000], axis=1)
            sums += np.sum(radial[:, None] ** q[None, :], axis=0)
        moments[j] = sums / len(xy)
        # Process a single coordinate at a time. Uniform inverse-CDF quantiles need
        # only in-place selection, not a second full-sized index/weight array.
        ranks = np.maximum(
            0, np.ceil(np.asarray(probabilities) * len(xy)).astype(int) - 1
        )
        for k in range(3):
            values = np.abs(xy[:, k]) if k < 2 else np.hypot(xy[:, 0], xy[:, 1])
            values.partition(ranks)
            quantiles[j, k] = values[ranks]
            del values
        kurtosis[j] = streamed_mardia(xy)
        print(
            f"full diagnostics: reduced lag {lags[j]} s, {len(xy)} increments",
            flush=True,
        )
    result = {
        "variations": variations,
        "moments": moments,
        "quantiles": quantiles,
        "mardia": kurtosis,
        "vectors": vectors,
        "owners": owners,
        "coarse": {
            s: np.divide(
                coarse_sum[s],
                coarse_count[s],
                out=np.full_like(coarse_sum[s], np.nan),
                where=coarse_count[s] > 0,
            )
            for s in scales
        },
        "coarse_support": coarse_count,
        "frame": pd.DataFrame(frames.rows),
        "_frames": frames,
    }
    return result


def streamed_mardia(xy, chunk_size=100000):
    """Compute the same centred fourth-order statistic with bounded temporaries."""
    n = len(xy)
    mean = np.zeros(2)
    for start in range(0, n, chunk_size):
        mean += np.sum(xy[start : start + chunk_size], axis=0) / n
    scatter = np.zeros((2, 2))
    for start in range(0, n, chunk_size):
        centered = xy[start : start + chunk_size] - mean
        scatter += centered.T @ centered
    covariance = scatter / n
    if np.linalg.matrix_rank(covariance) < 2:
        return float("nan")
    inverse = np.linalg.inv(covariance)
    fourth = 0.0
    for start in range(0, n, chunk_size):
        centered = xy[start : start + chunk_size] - mean
        distance = np.einsum("ij,jk,ik->i", centered, inverse, centered)
        fourth += float(np.sum(distance**2))
    return fourth / n - 8.0


def save_measurement(measured, directory):
    """Save compact summaries and references, never pickle mapped increment pools."""
    directory = Path(directory)
    small = {
        k: v for k, v in measured.items() if k not in {"vectors", "owners", "_frames"}
    }
    with (directory / "measurement.pkl").open("wb") as out:
        pickle.dump(small, out, protocol=5)
    (directory / "counts.json").write_text(
        json.dumps([len(v) for v in measured["vectors"]])
    )
    (directory / ".incomplete").unlink(missing_ok=True)


def load_measurement(directory):
    """Open saved summaries and lazily mapped per-lag pools."""
    directory = Path(directory)
    if (directory / ".incomplete").exists():
        raise ValueError("Full-archive cache is incomplete; rerun without --reuse")
    with (directory / "measurement.pkl").open("rb") as stream:
        measured = pickle.load(stream)
    counts = json.loads((directory / "counts.json").read_text())
    measured["vectors"] = [
        np.memmap(
            directory / f"vectors-{j}.bin", mode="r", dtype="float64", shape=(n, 2)
        )
        if n
        else np.empty((0, 2))
        for j, n in enumerate(counts)
    ]
    measured["owners"] = [
        np.memmap(directory / f"owners-{j}.bin", mode="r", dtype="int32", shape=(n,))
        if n
        else np.empty(0, dtype="int32")
        for j, n in enumerate(counts)
    ]
    measured["_frames"] = DiskFrames(directory)
    return measured


def archive_quantile_control(measured, frames, lags, probabilities, variants):
    """Reduce one population and lag at a time, sharing the saved full pools."""
    from .global_diagnostics import empirical_quantiles

    fixed = np.array([row["duration_s"] >= 20000 for row, _ in frames])
    fixed_indexes = np.flatnonzero(fixed)
    origins = {
        i: increment_starts(row, len(pos), int(lags[-1] // 10), stride=1)
        for i, (row, pos) in enumerate(frames)
        if fixed[i]
    }
    curves = np.full((4, len(lags), 3, len(probabilities)), np.nan)
    curves[0] = measured["quantiles"]
    flights = np.zeros((4, len(lags)), dtype=int)
    windows = np.zeros_like(flights)
    for j, tau in enumerate(lags):
        who = measured["owners"][j]
        sizes = np.bincount(who, minlength=len(frames))
        flights[0, j] = np.count_nonzero(sizes)
        windows[0, j] = len(who)
        selection = fixed[who]
        xy = measured["vectors"][j][selection]
        selected_owners = who[selection]
        weights = 1.0 / sizes[selected_owners]
        for k in range(3):
            values = np.abs(xy[:, k]) if k < 2 else np.hypot(xy[:, 0], xy[:, 1])
            if len(values) >= 30:
                curves[1, j, k] = empirical_quantiles(values[:, None], probabilities)[0]
                curves[2, j, k] = empirical_quantiles(
                    values[:, None], probabilities, weights
                )[0]
        flights[1:3, j] = np.count_nonzero(sizes[fixed])
        windows[1:3, j] = len(xy)
        del xy, selected_owners, weights, selection
        lag = int(tau // 10)
        sizes_fixed = np.array([len(origins[i]) for i in fixed_indexes])
        total = int(sizes_fixed.sum())
        xy = np.empty((total, 2))
        weights = np.empty(total)
        offset = 0
        for i in fixed_indexes:
            _, pos = frames[i]
            starts = origins[i]
            n = len(starts)
            xy[offset : offset + n] = pos[starts + lag] - pos[starts]
            weights[offset : offset + n] = 1.0 / n
            offset += n
        for k in range(3):
            values = np.abs(xy[:, k]) if k < 2 else np.hypot(xy[:, 0], xy[:, 1])
            if total >= 30:
                curves[3, j, k] = empirical_quantiles(
                    values[:, None], probabilities, weights
                )[0]
        flights[3, j], windows[3, j] = len(fixed_indexes), total
        print(f"population control: lag {tau} s", flush=True)
    return {
        "quantiles": curves,
        "flights_per_lag": flights,
        "windows_per_lag": windows,
        "fixed_flight_indexes": fixed_indexes,
        "fixed_origin_counts": np.array([len(origins[i]) for i in fixed_indexes]),
        "fixed_min_duration_s": 20000,
        "variants": variants,
    }


def region_geometry(xy, owners, selected_flights, chunk_size=100000):
    """Regional covariance and flight support without copying a whole region's pool."""
    seen = np.zeros(len(selected_flights), dtype=bool)
    count, total = 0, np.zeros(2)
    for start in range(0, len(xy), chunk_size):
        who = owners[start : start + chunk_size]
        keep = selected_flights[who]
        values = xy[start : start + chunk_size][keep]
        total += values.sum(axis=0)
        count += len(values)
        seen[who[keep]] = True
    n_flights = int(seen.sum())
    if count < 8 or n_flights < 8:
        return n_flights, {}
    mean = total / count
    scatter = np.zeros((2, 2))
    for start in range(0, len(xy), chunk_size):
        keep = selected_flights[owners[start : start + chunk_size]]
        centered = xy[start : start + chunk_size][keep] - mean
        scatter += centered.T @ centered
    covariance = scatter / count
    values, vectors = np.linalg.eigh(covariance)
    if values[0] <= 0:
        return n_flights, {}
    axis = vectors[:, -1]
    return n_flights, {
        "mean": mean,
        "covariance": covariance,
        "ratio": float(values[-1] / values[0]),
        "angle_deg": float(np.degrees(np.arctan2(axis[1], axis[0])) % 180),
        "correlation": float(
            covariance[0, 1] / np.sqrt(covariance[0, 0] * covariance[1, 1])
        ),
    }
