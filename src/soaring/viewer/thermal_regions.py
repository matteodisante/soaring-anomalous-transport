"""Climb-point density inside the five named regional boxes, prepared once offline.

A region spans hundreds of kilometres, so this reads each discipline's already-decoded
``segmentation/phase_points.parquet`` (HMM output) for the flights launching inside the
box (the population :func:`soaring.analysis.regions.region_box_masks` selects), bins
the lon/lat of their climb-phase fixes with every height pooled at 0.001 degrees
(about 100 m), and saves only the non-empty bins. The viewer opens that small file and
derives coarser levels (0.003, 0.01, 0.03 degrees) so a zoomed-out view stays light and
a zoomed-in one shows the fine grid; it never touches the archive.

No Qt import (see the package docstring).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from ..analysis.preproc.enu import LocalFrame
from ..analysis.regions import REGIONAL_BOXES
from ..reporting.disciplines import DISCIPLINES
from .geodesy import enu_to_geodetic

FILE_NAME = "thermal-regions.npz"
VERSION = 2

# (west, east, south, north). REGIONAL_BOXES lacks the Massif Central box that
# scripts/condivisi/generate_prelim_figure.py's OROGRAPHY defines and its map draws.
MASSIF_CENTRAL = (1.8, 4.6, 43.6, 46.2)
REGIONS = {**REGIONAL_BOXES, "Massif Central": MASSIF_CENTRAL}

FINE_DEG = 0.001
# Bins of each level per finest bin, coarsest first.
FACTORS = (30, 10, 3, 1)
PAD_DEG = 0.3


def extent(box) -> tuple[float, float, float, float]:
    """``(lon_min, lat_min, lon_max, lat_max)`` of the padded map frame for ``box``."""
    west, east, south, north = box
    return west - PAD_DEG, south - PAD_DEG, east + PAD_DEG, north + PAD_DEG


def grid_shape(box) -> tuple[int, int]:
    """Finest-grid ``(ny, nx)``, a multiple of the coarsest factor in each axis."""
    lon_min, lat_min, lon_max, lat_max = extent(box)
    top = FACTORS[0]
    nx = int(np.ceil((lon_max - lon_min) / (FINE_DEG * top))) * top
    ny = int(np.ceil((lat_max - lat_min) / (FINE_DEG * top))) * top
    return ny, nx


class RegionDensity:
    """Non-empty finest bins of one region, viewable at any zoom."""

    def __init__(self, box, flat: np.ndarray, counts: np.ndarray):
        """Keep the sparse bins; coarser dense levels are built on first use."""
        self.box = box
        self.ny, self.nx = grid_shape(box)
        self.lon0, self.lat0 = extent(box)[:2]
        self.flat = flat.astype(np.int64)
        self.counts = counts.astype(np.float64)
        self.rows, self.cols = np.divmod(self.flat, self.nx)
        self.points = int(self.counts.sum())
        self._levels: dict[int, np.ndarray] = {}

    def _dense(self, factor: int) -> np.ndarray:
        if factor not in self._levels:
            ny, nx = self.ny // factor, self.nx // factor
            index = (self.rows // factor) * nx + self.cols // factor
            self._levels[factor] = np.bincount(
                index, weights=self.counts, minlength=ny * nx
            ).reshape(ny, nx)
        return self._levels[factor]

    def window(self, x0, x1, y0, y1, bins=1000):
        """Counts over the view at the coarsest level with at least ``bins`` across.

        Returns ``(counts[lat, lon], lon_edges, lat_edges, size_deg)``, snapped to the
        level's grid and clipped to the saved frame.
        """
        factor = next(
            (f for f in FACTORS if (x1 - x0) / (FINE_DEG * f) >= bins), FACTORS[-1]
        )
        size = FINE_DEG * factor
        c0 = int(np.clip(np.floor((x0 - self.lon0) / size), 0, self.nx // factor))
        c1 = int(np.clip(np.ceil((x1 - self.lon0) / size), 0, self.nx // factor))
        r0 = int(np.clip(np.floor((y0 - self.lat0) / size), 0, self.ny // factor))
        r1 = int(np.clip(np.ceil((y1 - self.lat0) / size), 0, self.ny // factor))
        if factor != 1:
            counts = self._dense(factor)[r0:r1, c0:c1]
        else:
            inside = (
                (self.rows >= r0)
                & (self.rows < r1)
                & (self.cols >= c0)
                & (self.cols < c1)
            )
            counts = np.zeros((max(r1 - r0, 0), max(c1 - c0, 0)))
            np.add.at(
                counts,
                (self.rows[inside] - r0, self.cols[inside] - c0),
                self.counts[inside],
            )
        return (
            counts,
            self.lon0 + np.arange(c0, c1 + 1) * size,
            self.lat0 + np.arange(r0, r1 + 1) * size,
            size,
        )


def cache_path() -> Path:
    """Beside the thermal-plane store, on the archive disk."""
    override = os.environ.get("SOARING_VIEWER_CACHE_DIR")
    if override:
        return Path(override).expanduser() / FILE_NAME
    for disc in DISCIPLINES.values():
        derived = disc.derived_dir()
        if derived is not None:
            return derived / "viewer/thermal-planes" / FILE_NAME
    raise FileNotFoundError("Connect the SSD containing the processed archives")


def _accumulate(disc, meta, box, dense, progress):
    """Add one discipline's climb fixes (launched in ``box``) to ``dense``."""
    west, east, south, north = box
    inside = meta.lon0.between(west, east) & meta.lat0.between(south, north)
    ids = meta.loc[inside.fillna(False), "flight_id"]
    path = disc.config().derived_dir / "segmentation" / "phase_points.parquet"
    if ids.empty or not path.is_file():
        return
    points = pd.read_parquet(
        path,
        columns=["flight_id", "E", "N", "z", "phase"],
        filters=[("flight_id", "in", ids.tolist())],
    )
    points = points.loc[points.phase == "climb"].copy()
    points["flight_id"] = points.flight_id.astype(str)
    frames = meta.drop_duplicates("flight_id", keep="last").set_index("flight_id")
    ny, nx = dense.shape
    lon_min, lat_min = extent(box)[:2]
    pending, waiting = [], 0

    def flush():
        nonlocal pending, waiting
        if pending:
            unique, counts = np.unique(np.concatenate(pending), return_counts=True)
            dense.reshape(-1)[unique] += counts.astype(np.uint32)
        pending, waiting = [], 0

    for done, (fid, group) in enumerate(points.groupby("flight_id", sort=False)):
        if fid not in frames.index:
            continue
        lat0, lon0, alt0 = frames.loc[fid, ["lat0", "lon0", "alt0"]]
        lat, lon = enu_to_geodetic(
            group.E.to_numpy(),
            group.N.to_numpy(),
            group.z.to_numpy(),
            LocalFrame(lat0, lon0, alt0),
        )
        col = np.floor((lon - lon_min) / FINE_DEG).astype(np.int64)
        row = np.floor((lat - lat_min) / FINE_DEG).astype(np.int64)
        keep = (col >= 0) & (col < nx) & (row >= 0) & (row < ny)
        pending.append(row[keep] * nx + col[keep])
        waiting += int(keep.sum())
        if waiting > 2_000_000:
            flush()
        if done % 5000 == 0:
            progress(f"  {done:,} flights binned")
    flush()


def prepare_regions(progress: Callable[[str], None] = lambda _: None) -> Path:
    """Bin every region's climb points and atomically write the small result file."""
    discs = [d for d in DISCIPLINES.values() if d.derived_dir() is not None]
    if not discs:
        raise FileNotFoundError("Connect the SSD containing the processed archives")
    metas = []
    for disc in discs:
        meta = pd.read_parquet(
            disc.config().derived_dir / "flights_meta.parquet",
            columns=["flight_id", "lat0", "lon0", "alt0"],
        )
        meta["flight_id"] = meta.flight_id.astype(str)
        metas.append((disc, meta))
    arrays = {"version": np.array(VERSION)}
    for i, (name, box) in enumerate(REGIONS.items()):
        dense = np.zeros(grid_shape(box), dtype=np.uint32)
        for disc, meta in metas:
            progress(f"{name}: {disc.name}")
            _accumulate(disc, meta, box, dense, progress)
        flat = np.flatnonzero(dense)
        arrays[f"flat_{i}"] = flat.astype(np.uint32)
        arrays[f"count_{i}"] = dense.reshape(-1)[flat]
        progress(f"{name}: {int(dense.sum()):,} climb fixes in {len(flat):,} bins")
    target = cache_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(".building-" + target.name)
    with temporary.open("wb") as out:
        np.savez_compressed(out, **arrays)
    temporary.replace(target)
    return target


def load_regions() -> dict[str, RegionDensity] | None:
    """Saved ``{region: RegionDensity}``, or ``None`` if not prepared."""
    try:
        path = cache_path()
    except FileNotFoundError:
        return None
    if not path.is_file():
        return None
    with np.load(path, allow_pickle=False) as saved:
        if "version" not in saved or int(saved["version"]) != VERSION:
            return None
        return {
            name: RegionDensity(box, saved[f"flat_{i}"], saved[f"count_{i}"])
            for i, (name, box) in enumerate(REGIONS.items())
        }
