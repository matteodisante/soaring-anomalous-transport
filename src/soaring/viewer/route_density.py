"""All-archive HMM residence time, shared in definition with Thermal density.

One sparse 50 m grid covers France and its surroundings. Route selection never
filters this background. Only a bounded, conservatively aggregated raster enters
the 3-D scene; neither trajectories nor dense continental rasters are duplicated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from ..analysis.segmentation.config import load_segmentation_config
from .route_index import available_archives, route_cache_path
from .thermal_index import _check_cancel
from .thermal_time import BASE_M, TimeGrid, load_grids, save_grids
from .thermal_time_prepare import phase_edges

# 2.5 billion possible pixels, within save_grids' uint32 index limit; only
# occupied pixels are stored. This also covers excursions beyond French borders.
BOUNDS = (-500000, 5500000, 2000000, 8000000)
FILE_NAME = "route-thermal-duration.npz"


def density_path(disciplines=None):
    """Keep the all-flight thermal product beside the route index on the SSD."""
    return route_cache_path(disciplines).with_name(FILE_NAME)


def source_signature(disciplines):
    """Bind saved seconds to the classified archives, origins and calculation."""
    parts = [load_segmentation_config().decision_step_s]
    for name in (
        "geodesy.py",
        "thermal_time.py",
        "thermal_time_prepare.py",
        "route_density.py",
    ):
        parts.append(
            hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        )
    for disc in disciplines:
        root = disc.config().derived_dir
        if (root / ".run_incomplete").exists():
            raise ValueError(f"{disc.name}: preprocessing is incomplete")
        for name in (
            "segmentation/phase_points.parquet",
            "flights_meta.parquet",
            "fixes.parquet",
        ):
            path = root / name
            stat = path.stat()
            parts.append((str(path.resolve()), stat.st_size, stat.st_mtime_ns))
        if (root / "segmentation/phase_points.parquet").stat().st_mtime_ns < (
            root / "fixes.parquet"
        ).stat().st_mtime_ns:
            raise ValueError(
                f"{disc.name}: HMM classifications predate the cleaned archive"
            )
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()


def prepare_density(
    disciplines=None, *, path=None, progress=lambda _: None, cancel=None
):
    """Stream each saved HMM archive once; reuse a complete matching product."""
    import fcntl

    disciplines = available_archives() if disciplines is None else disciplines
    if not disciplines:
        raise FileNotFoundError("Connect the processed flight archive")
    path = density_path(disciplines) if path is None else Path(path)
    signature = source_signature(disciplines)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if path.exists():
            with np.load(path, allow_pickle=False) as saved:
                info = json.loads(str(saved["metadata"]))
                if info.get("complete") and info.get("signature") == signature:
                    return path
        grid = TimeGrid(
            BOUNDS,
            metadata={"population": "all crossing archived flights", "source": "HMM"},
        )
        stages = {}
        for disc in disciplines:
            _check_cancel(cancel)
            root = disc.config().derived_dir
            meta = pd.read_parquet(
                root / "flights_meta.parquet",
                columns=["flight_id", "lat0", "lon0", "alt0"],
            )
            origins = {
                str(r.flight_id): (r.lat0, r.lon0, r.alt0)
                for r in meta.itertuples(index=False)
            }
            archive = pq.ParquetFile(root / "segmentation/phase_points.parquet")
            previous = None
            rows = edges = 0
            for batch in archive.iter_batches(
                batch_size=131072,
                columns=["flight_id", "segment_id", "t", "E", "N", "z", "phase"],
            ):
                _check_cancel(cancel)
                frame = batch.to_pandas()
                rows += len(frame)
                if previous is not None:
                    frame = pd.concat([previous, frame], ignore_index=True)
                previous = frame.iloc[-1:].copy()
                a, b, seconds = phase_edges(
                    frame, origins, 1.5 * load_segmentation_config().decision_step_s
                )
                grid.add(a, b, seconds)
                edges += len(seconds)
                progress(
                    f"Thermal hours · {disc.name}: "
                    f"{rows:,}/{archive.metadata.num_rows:,} decisions"
                )
            stages[disc.name] = {"rows": rows, "edges": edges}
        _check_cancel(cancel)
        if source_signature(disciplines) != signature:
            raise ValueError("Thermal source archive changed during preparation")
        save_grids(
            {"archive/own": grid},
            path,
            {
                "complete": True,
                "signature": signature,
                "stages": stages,
                "created": datetime.now(UTC).isoformat(),
                "base_m": BASE_M,
                "method": "HMM consecutive climb decisions; "
                "same calculation as Thermal density regions",
            },
        )
    return path


@dataclass
class DensityRaster:
    """South-first hours/km² and its uniform metric footprint."""

    values: np.ndarray
    bounds: np.ndarray
    step: float
    hours: float
    maximum: float
    metadata: dict


@dataclass
class DensityAtlas:
    """A few bounded overview resolutions from the same all-flight time grid."""

    rasters: dict[float, DensityRaster]


def raster_window(grid, bounds, *, bins=700, pixel_m=None, metadata=None):
    """Sum fine-cell seconds into aligned overview pixels, conserving their time."""
    bounds = np.asarray(bounds, float)
    if (bounds[:2] < grid.bounds[:2]).any() or (bounds[2:] > grid.bounds[2:]).any():
        raise ValueError(
            "Route exceeds the prepared thermal coverage (France and surroundings)"
        )
    factor = 2 ** max(
        0,
        int(np.ceil(np.log2(max(max(bounds[2:] - bounds[:2]) / bins / grid.step, 1)))),
    )
    if pixel_m is not None:
        factor = max(1, round(pixel_m / grid.step))
    step = grid.step * factor
    origin = grid.bounds[:2]
    lo = np.floor((bounds[:2] - origin) / step).astype(int)
    hi = np.ceil((bounds[2:] - origin) / step).astype(int)
    raster_bounds = np.r_[origin + lo * step, origin + hi * step]
    nx, ny = hi - lo
    values = np.zeros((ny, nx))
    # Slice sorted sparse row indices before materialising coordinate arrays.
    r0 = max(0, lo[1] * factor)
    r1 = min(grid.ny, hi[1] * factor)
    first, last = np.searchsorted(grid.flat, [r0 * grid.nx, r1 * grid.nx])
    rows, cols = np.divmod(grid.flat[first:last], grid.nx)
    rows, cols = rows // factor - lo[1], cols // factor - lo[0]
    inside = (cols >= 0) & (cols < nx)
    np.add.at(values, (rows[inside], cols[inside]), grid.seconds[first:last][inside])
    hours = float(values.sum() / 3600)
    values /= 3600 * (step / 1000) ** 2
    maximum = max(
        1.0, float(grid.seconds.max(initial=0)) / 3600 / (grid.step / 1000) ** 2
    )
    return DensityRaster(values, raster_bounds, step, hours, maximum, metadata or {})


def load_density(bounds, disciplines=None, *, path=None):
    """Read the all-flight source and return only the small scene raster."""
    disciplines = available_archives() if disciplines is None else disciplines
    path = density_path(disciplines) if path is None else path
    grids, metadata = load_grids(path)
    if metadata.get("signature") != source_signature(disciplines):
        raise ValueError("Thermal archive changed; use Prepare / refresh index")
    grid = grids["archive/own"]
    span = max(np.asarray(bounds[2:]) - bounds[:2])
    steps = [step for step in (250, 500, 1000, 2000) if span / step <= 1600]
    if not steps:
        steps = [BASE_M * np.ceil(span / 1600 / BASE_M)]
    return DensityAtlas(
        {
            step: raster_window(grid, bounds, pixel_m=step, metadata=metadata)
            for step in steps
        }
    )
