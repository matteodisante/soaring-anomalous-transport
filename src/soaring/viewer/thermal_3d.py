"""Verified terrain and saved 20 m climb intersections for any prepared cell."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .thermal_daily import height_levels
from .thermal_geometry import ThermalCell
from .thermal_ground import mean_terrain
from .thermal_orography import DATA_DIRECTORY
from .thermal_store import CancelledError


@dataclass(frozen=True)
class TerrainScene:
    """Metres east/north of the cell centre, with absolute altitude in metres."""

    cell: ThermalCell
    x: np.ndarray
    y: np.ndarray
    terrain: np.ndarray
    points: np.ndarray
    reference: dict
    climb_runs: int
    contributing_flights: int
    selected_flights: int
    unavailable_flights: int
    unclassified_flights: int
    unknown_clock_flights: int
    start: float
    end: float
    label: str = ""


def cell_label(store, cell):
    """Validate the selected saved cell and identify its Vilpellet category rank."""
    if not store.has_climb_ranking:
        raise ValueError("The 3D view requires the Vilpellet climb-ranked snapshot")
    cells = sorted(
        (c for c in store.cells() if c.terrain == cell.terrain),
        key=lambda c: (-store.activity_counts[c.ix, c.iy]["climb_runs"], c.ix, c.iy),
    )
    if cell not in cells:
        raise ValueError(
            "The selected cell is missing or changed in the prepared snapshot"
        )
    return f"{cell.terrain} #{cells.index(cell) + 1}"


def read_surface(store, cell):
    """Read the original IGN floats, checking the snapshot hash and coordinates.

    Files remain offline. Raster rows initially run north to south; return a
    south-to-north mesh. Extend the outer half-pixel to the cell boundary with
    the nearest elevation, so the displayed surface covers the complete square.
    """
    reference = store.terrain_reference(cell)
    name = f"ign-terrain-{cell.ix}-{cell.iy}.tif"
    candidates = (
        store.path.parent / "exploration/terrain" / name,
        DATA_DIRECTORY / name,
    )
    expected = reference["response_sha256"]
    raw = None
    for path in candidates:
        if path.is_file():
            candidate = path.read_bytes()
            if hashlib.sha256(candidate).hexdigest() == expected:
                raw = candidate
                break
    if raw is None:
        raise ValueError(
            f"The verified IGN elevation raster {name} is missing or changed. "
            "Restore it in the SSD exploration/terrain folder."
        )
    if tuple(reference["bounds_epsg2154"]) != cell.bounds:
        raise ValueError("Terrain reference belongs to a different cell")
    with Image.open(io.BytesIO(raw)) as im:
        if im.mode != "F":
            raise ValueError(
                "The terrain raster must contain floating-point elevations"
            )
        z = np.asarray(im).copy()
    bounds = reference["raster_bounds_epsg2154"]
    summary = mean_terrain(z, bounds, cell.bounds)
    if not np.isclose(summary["mean_m"], cell.ground_m, rtol=0, atol=1e-5):
        raise ValueError("DEM mean differs from the saved intersection reference")
    west, south, east, north = cell.bounds
    w, s, e, n = bounds
    dx, dy = (e - w) / z.shape[1], (n - s) / z.shape[0]
    x = w + (np.arange(z.shape[1]) + 0.5) * dx
    y = n - (np.arange(z.shape[0]) + 0.5) * dy
    cols = (x >= west) & (x < east)
    rows = (y >= south) & (y < north)
    z = z[np.ix_(rows, cols)][::-1]
    x, y = x[cols], y[rows][::-1]
    if min(z.shape) < 2:
        raise ValueError("The terrain grid is too small to form a surface")
    x = np.r_[west, x, east] - (west + east) / 2
    y = np.r_[south, y, north] - (south + north) / 2
    return x, y, np.pad(z, 1, mode="edge"), reference


def points_every_20m(frame, cell, start, end):
    """Select true 20 m levels, including neither odd levels nor an off-grid ceiling.

    The saved level is an index, not an altitude. The last 10 m lattice entry
    can be an irregular exact ceiling, so index parity alone is insufficient.
    Time and cell masks match the 2D plane view. No point is randomly thinned.
    """
    if frame is None:
        raise ValueError("Saved intersection levels are required for the 3D view")
    if frame.empty:
        return np.empty((0, 3), dtype=np.float32), 0
    levels = height_levels(cell.max_agl_m)
    indices = frame.level.to_numpy(dtype=float)
    if (
        not np.isfinite(indices).all()
        or (indices != np.floor(indices)).any()
        or (indices < 0).any()
        or (indices >= len(levels)).any()
    ):
        raise ValueError("Invalid saved intersection level")
    heights = levels[indices.astype(int)]
    west, south, east, north = cell.bounds
    keep = (
        np.isclose(heights / 20, np.round(heights / 20), rtol=0, atol=1e-8)
        & frame.x.between(west, east, inclusive="left").to_numpy()
        & frame.y.between(south, north, inclusive="left").to_numpy()
        & frame.utc.between(start, end).to_numpy()
    )
    selected = frame.loc[keep]
    xyz = np.column_stack(
        (
            selected.x.to_numpy() - (west + east) / 2,
            selected.y.to_numpy() - (south + north) / 2,
            cell.ground_m + heights[keep],
        )
    ).astype(np.float32)
    flights = len(selected[["discipline", "flight_id"]].drop_duplicates())
    return xyz, flights


def load_scene(store, cell, start, end, *, progress=lambda _: None, cancel=None):
    """Load the selected saved cell, Vilpellet and the requested UTC interval."""
    if not np.isfinite([start, end]).all() or end < start:
        raise ValueError("Choose a valid time interval in Thermal planes")
    if not store.has_points:
        raise ValueError("Prepare the saved 10 m intersection lattice first")

    def check_cancel():
        if cancel is not None and cancel.is_set():
            raise CancelledError("Cancelled")

    check_cancel()
    label = cell_label(store, cell)
    progress(f"Reading verified IGN terrain for {label}…")
    x, y, terrain, reference = read_surface(store, cell)
    check_cancel()
    progress("Reading saved Vilpellet intersections for the selected dates…")
    plane = store.read_plane(
        cell, start, end, "vilpellet", progress=progress, cancel=cancel
    )
    check_cancel()
    points, flights = points_every_20m(plane.points, cell, start, end)
    return TerrainScene(
        cell,
        x,
        y,
        terrain,
        points,
        reference,
        store.activity_counts[cell.ix, cell.iy]["climb_runs"],
        flights,
        plane.selected,
        plane.unavailable,
        plane.unclassified,
        plane.unknown_clock,
        start,
        end,
        label,
    )
