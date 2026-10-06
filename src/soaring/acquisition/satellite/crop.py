"""Crop the SEVIRI rapid-scan archive to the cell windows and write it to disk.

Every downloaded chunk lives only in memory: it is cut to the windows and
dropped. One output file per month holds both kinds (``nonhrv``, ``hrv``) for
every cell; it is written to a temporary name and renamed, so a file that
exists is complete, and an interrupted run resumes at the first missing month.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time as clock
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from soaring.acquisition.satellite.config import Config
from soaring.acquisition.satellite.grid import Box, pixel_box, window_outline
from soaring.acquisition.satellite.ocf import (
    SCALING,
    SEVIRI_RSS,
    Fetcher,
    OcfStore,
    assemble,
    needed_chunks,
)

KINDS = ("nonhrv", "hrv")
SOURCE = "seviri-rss-ocf"


@dataclass
class Crop:
    """Cropped images of one kind for every cell.

    Attributes:
        time: UTC time of each kept step, ``datetime64[ns]``.
        variables: Channel names.
        units: Unit of each channel.
        boxes: Static-grid pixel rectangle of each cell.
        x: Column coordinates of each cell's box (geostationary metres).
        y: Row coordinates of each cell's box (geostationary metres).
        data: ``(time, rows, cols, channels)`` float16 per cell.
        dropped: Kept-hour steps discarded for unusable HRV coordinates.
    """

    time: np.ndarray
    variables: tuple[str, ...]
    units: dict[str, str]
    boxes: dict[str, Box]
    x: dict[str, np.ndarray]
    y: dict[str, np.ndarray]
    data: dict[str, np.ndarray] = field(default_factory=dict)
    dropped: int = 0


def local_mask(times: np.ndarray, tz: str, hours: tuple[int, int]) -> np.ndarray:
    """True for UTC ``times`` whose local hour lies in ``[hours[0], hours[1])``."""
    zone = ZoneInfo(tz)
    seconds = times.astype("datetime64[s]").astype(np.int64)
    local = np.array(
        [datetime.fromtimestamp(s, UTC).astimezone(zone).hour for s in seconds]
    )
    return (local >= hours[0]) & (local < hours[1])


def crop_days(
    cfg: Config, store: OcfStore, days: list[date], fetcher: Fetcher, workers: int = 16
) -> Crop:
    """Cut every cell window out of ``store`` for the kept hours of ``days``."""
    outlines = {c.name: window_outline(cfg, c) for c in cfg.cells}
    boxes = {
        n: pixel_box(SEVIRI_RSS, lon, lat, store.x, store.y)
        for n, (lon, lat) in outlines.items()
    }
    day_of = store.time.astype("datetime64[D]")
    wanted = np.isin(day_of, np.array(days, dtype="datetime64[D]"))
    wanted &= local_mask(store.time, cfg.local_timezone, cfg.local_hours)
    rows = np.flatnonzero(wanted)
    steps_per_chunk = 12
    chunks = sorted(set(rows // steps_per_chunk))

    def one_chunk(t: int) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        steps = rows[rows // steps_per_chunk == t] - t * steps_per_chunk
        shifts = store.hrv_shifts(t)
        keys = set()
        for box in boxes.values():
            keys |= needed_chunks(box, shifts, steps, store.chunk_yx, store.n_chunks_yx)
        got = {key: store.data_chunk(t, *key) for key in keys}
        usable = steps[np.isfinite(shifts[steps])]
        cut = {
            n: assemble(
                lambda j, i: got.get((j, i)),
                box,
                usable,
                shifts,
                store.chunk_yx,
                store.n_chunks_yx,
                len(store.variables),
            )
            for n, box in boxes.items()
        }
        return usable + t * steps_per_chunk, cut

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(one_chunk, chunks))
    kept = np.concatenate([r for r, _ in results]) if results else np.array([], int)
    crop = Crop(
        time=store.time[kept],
        variables=store.variables,
        units=store.units,
        boxes=boxes,
        x={n: store.x.values(b.c0, b.c1) for n, b in boxes.items()},
        y={n: store.y.values(b.r0, b.r1) for n, b in boxes.items()},
        dropped=len(rows) - len(kept),
    )
    for n, box in boxes.items():
        parts = [cut[n] for _, cut in results]
        crop.data[n] = (
            np.concatenate(parts)
            if parts
            else np.empty(
                (0, box.r1 - box.r0, box.c1 - box.c0, len(store.variables)), np.float16
            )
        )
    return crop


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write_crops(path: Path, cfg: Config, crops: dict[str, Crop], stats: dict) -> Path:
    """Write ``crops`` to ``path`` atomically, after checking the free space."""
    path.parent.mkdir(parents=True, exist_ok=True)
    free_gib = shutil.disk_usage(path.parent).free / 2**30
    if free_gib < cfg.min_free_gib:
        raise RuntimeError(
            f"Only {free_gib:.1f} GiB free on {path.parent}; "
            f"stopping before writing (min_free_gib={cfg.min_free_gib})"
        )
    arrays: dict[str, np.ndarray] = {}
    for kind, crop in crops.items():
        arrays[f"{kind}__time"] = crop.time.astype("datetime64[ns]").astype(np.int64)
        arrays[f"{kind}__variables"] = np.array(crop.variables)
        for name in crop.data:
            arrays[f"{name}__{kind}"] = crop.data[name]
            arrays[f"{name}__{kind}__x"] = crop.x[name]
            arrays[f"{name}__{kind}__y"] = crop.y[name]
    meta = {
        "source": SOURCE,
        "projection": SEVIRI_RSS.srs,
        "time": "UTC, nanoseconds since 1970-01-01",
        "values": "OCF scaling clip((v - min) / (max - min), 0, 1); physical "
        "v = min + value * (max - min), see ocf.to_physical",
        "scaling": {
            kind: {v: SCALING[v] for v in crop.variables}
            for kind, crop in crops.items()
        },
        "physical_units": {kind: crop.units for kind, crop in crops.items()},
        "cells": [
            {"name": c.name, "ix": c.ix, "iy": c.iy, "terrain": c.terrain}
            for c in cfg.cells
        ],
        "window": vars(cfg.window),
        "local_timezone": cfg.local_timezone,
        "local_hours": list(cfg.local_hours),
        "dropped_steps": {k: c.dropped for k, c in crops.items()},
        "written_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "code_commit": _git_commit(),
        **stats,
    }
    arrays["meta"] = np.array(json.dumps(meta))
    tmp = path.with_name(path.name + ".partial.npz")
    np.savez_compressed(tmp, **arrays)
    tmp.replace(path)
    return path


def crop_and_write(
    cfg: Config,
    days: list[date],
    path: Path,
    fetcher: Fetcher,
    stores: dict[tuple[int, str], OcfStore],
    workers: int = 16,
    progress: Callable[[str], None] = print,
) -> dict:
    """Crop both kinds for ``days`` (all in one year) and write them to ``path``.

    ``stores`` caches opened stores by ``(year, kind)``, so the months of one year
    read the store's time steps and axes once.
    """
    years = {d.year for d in days}
    if len(years) != 1:
        raise ValueError("All days must fall in one year (one store per year)")
    year = years.pop()
    bytes0, requests0 = fetcher.bytes, fetcher.requests
    start = clock.monotonic()
    crops = {}
    for kind in KINDS:
        if (year, kind) not in stores:
            stores[year, kind] = OcfStore(year, kind, fetcher, workers)
        crops[kind] = crop_days(cfg, stores[year, kind], days, fetcher, workers)
        progress(
            f"{kind}: {len(crops[kind].time)} steps, "
            f"{(fetcher.bytes - bytes0) / 1e9:.2f} GB downloaded so far"
        )
    stats = {
        "days": [d.isoformat() for d in days],
        "downloaded_bytes": fetcher.bytes - bytes0,
        "requests": fetcher.requests - requests0,
        "elapsed_s": round(clock.monotonic() - start, 1),
    }
    write_crops(path, cfg, crops, stats)
    stats["written_bytes"] = path.stat().st_size
    return stats
