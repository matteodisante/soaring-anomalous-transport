"""Regional densities of climb crossings through horizontal planes every 10 m.

Use the viewer's native-edge continuity and intersection routines. Every crossing
counts, including several crossings from one flight in one horizontal bin. The
regional C10000 cohorts and archived own-HMM labels match the regional H comparison.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pyproj import Transformer

from soaring.analysis.preproc.enu import WGS84_A_M, WGS84_E2, geodetic_to_ecef
from soaring.analysis.derived import stream_flights
from soaring.analysis.regions import REGIONAL_BOXES
from soaring.viewer.geodesy import _ecef_to_geodetic
from soaring.viewer.thermal_geometry import continuous_edges
from soaring.viewer.thermal_daily import lattice_points

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "assets/regional-climb"
SOURCE = Path("/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917/para")
DERIVED = Path("/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/derived")
PHASE_SEGMENTS = DERIVED / "segmentation/phase_segments.parquet"
FIXES = DERIVED / "fixes.parquet"
REGIONS = ("Alps", "Pyrenees", "Channel Coast", "Champagne-Lorraine")
CELL_M = 1000
TO_LAMBERT = Transformer.from_crs(4326, 2154, always_xy=True)


def cohort() -> pd.DataFrame:
    columns = ["flight_id", "lon0", "lat0", "alt0", "task", "cohort_10000"]
    flights = pd.read_parquet(SOURCE / "flights.parquet", columns=columns)
    flights = flights.loc[flights.cohort_10000].copy()
    frames = []
    for index, name in enumerate(REGIONS):
        west, east, south, north = REGIONAL_BOXES[name]
        mask = flights.lon0.between(west, east) & flights.lat0.between(south, north)
        mask &= flights.alt0.ge(800) if index < 2 else flights.alt0.lt(800)
        region = flights.loc[mask].copy()
        region["region_index"] = index
        frames.append(region)
    selected = pd.concat(frames, ignore_index=True)
    assert selected.flight_id.is_unique
    return selected.set_index("flight_id")


def to_lambert(points: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Invert the same WGS84 fixed ENU frame used by the cleaned trajectories."""
    lat0 = np.radians(points.lat0.to_numpy(dtype=float))
    lon0 = np.radians(points.lon0.to_numpy(dtype=float))
    alt0 = points.alt0.to_numpy(dtype=float)
    east = points.E.to_numpy(dtype=float)
    north = points.N.to_numpy(dtype=float)
    z = points.z.to_numpy(dtype=float)
    sin_lat, cos_lat = np.sin(lat0), np.cos(lat0)
    sin_lon, cos_lon = np.sin(lon0), np.cos(lon0)
    radius = WGS84_A_M / np.sqrt(1 - WGS84_E2 * sin_lat**2)
    up = z - alt0 - (east**2 + north**2) / (2 * radius)
    x0, y0, z0 = geodetic_to_ecef(np.degrees(lat0), np.degrees(lon0), alt0)
    x = x0 - sin_lon * east - sin_lat * cos_lon * north + cos_lat * cos_lon * up
    y = y0 + cos_lon * east - sin_lat * sin_lon * north + cos_lat * sin_lon * up
    zz = z0 + cos_lat * north + sin_lat * up
    lat, lon, _ = _ecef_to_geodetic(x, y, zz)
    return TO_LAMBERT.transform(lon, lat)


@dataclass(frozen=True)
class RegionalPlanes:
    """An uncropped regional plane stack with an absolute 10 m altitude lattice.

    The viewer's cell-local AGL zero is replaced with a multiple of 10 m ASL.
    Rounded bounds keep its extra terminal plane on that same regular lattice.
    """

    ground_m: float
    max_agl_m: float
    bounds: tuple[float, float, float, float] = (-np.inf, -np.inf, np.inf, np.inf)


def climb_runs(selected: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Read the archived half-open decision intervals used to label native fixes."""
    ids = pc.SetLookupOptions(value_set=pa.array(selected.index.to_numpy(dtype=str)))
    frames = []
    columns = ["flight_id", "segment_id", "phase", "t_start", "t_end", "n_points"]
    for batch in pq.ParquetFile(PHASE_SEGMENTS).iter_batches(columns=columns):
        keep = pc.and_(pc.equal(batch.column("phase"), "climb"),
                       pc.is_in(batch.column("flight_id"), options=ids))
        if pc.any(keep).as_py():
            frames.append(batch.filter(keep).to_pandas())
    runs = pd.concat(frames, ignore_index=True)
    # A run must cover consecutive 10 s HMM decision cells; never bridge a gap.
    assert np.allclose(runs.t_end - runs.t_start, runs.n_points * 10)
    return {str(fid): frame for fid, frame in runs.groupby("flight_id", sort=False)}


def native_climb_edges(flight: pd.DataFrame, runs: pd.DataFrame, origin) -> np.ndarray:
    """Join only adjacent native fixes inside the same continuous climb interval."""
    flight = flight.sort_values(["segment_id", "t"], kind="stable").reset_index(drop=True)
    run_id = np.full(len(flight), -1, dtype=int)
    for segment_id, group in flight.groupby("segment_id", sort=False):
        intervals = runs.loc[runs.segment_id.eq(segment_id)].sort_values("t_start")
        if intervals.empty:
            continue
        times = group.t.to_numpy(dtype=float)
        positions = np.searchsorted(intervals.t_start.to_numpy(), times, side="right") - 1
        safe = np.clip(positions, 0, len(intervals) - 1)
        inside = (positions >= 0) & (times < intervals.t_end.to_numpy()[safe])
        run_id[group.index[inside]] = intervals.index.to_numpy()[safe[inside]]
    use = continuous_edges(flight) & (run_id[:-1] >= 0) & (run_id[:-1] == run_id[1:])
    finite = np.isfinite(flight[["E", "N", "z", "t"]].to_numpy()).all(axis=1)
    use &= finite[:-1] & finite[1:]
    starts = np.flatnonzero(use)
    if not len(starts):
        return np.empty((0, 8))
    vertices = np.unique(np.r_[starts, starts + 1])
    tab = flight.iloc[vertices].copy()
    for name in ("lat0", "lon0", "alt0"):
        tab[name] = origin[name]
    x, y = to_lambert(tab)
    values = np.column_stack((x, y, tab.z, tab.t))
    return np.column_stack((values[np.searchsorted(vertices, starts)],
                            values[np.searchsorted(vertices, starts + 1)]))


def crossing_points(edges: np.ndarray) -> np.ndarray:
    """Pool all 10 m planes using the viewer's exact crossing implementation."""
    if not len(edges):
        return np.empty((0, 4))
    z = edges[:, [2, 6]]
    bottom = float(np.floor(z.min() / 10) * 10)
    top = float(np.ceil(z.max() / 10) * 10)
    return lattice_points(edges, RegionalPlanes(bottom, top - bottom))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    selected = cohort()
    runs = climb_runs(selected)
    print(f"Loaded climb intervals for {len(runs):,} selected flights", flush=True)
    cells = [Counter() for _ in REGIONS]
    totals = np.zeros(len(REGIONS), dtype=np.int64)
    contributors = np.zeros(len(REGIONS), dtype=np.int64)
    native_edges = np.zeros(len(REGIONS), dtype=np.int64)
    found = set()
    columns = ["flight_id", "segment_id", "t", "E", "N", "z"]
    for number, flight in enumerate(stream_flights(FIXES, columns=columns), 1):
        fid = str(flight.flight_id.iloc[0])
        if fid in selected.index:
            found.add(fid)
        if fid in runs:
            origin = selected.loc[fid]
            region = int(origin.region_index)
            edges = native_climb_edges(flight, runs[fid], origin)
            points = crossing_points(edges)
            native_edges[region] += len(edges)
            totals[region] += len(points)
            contributors[region] += bool(len(points))
            if len(points):
                bins = np.floor(points[:, 1:3] / CELL_M).astype(np.int64)
                keys, counts = np.unique(bins, axis=0, return_counts=True)
                cells[region].update({tuple(key): int(n) for key, n in zip(keys, counts)})
        if number % 2000 == 0:
            print(f"Read {number:,} flights; {len(found):,}/{len(selected):,} cohort flights; "
                  f"{totals.sum():,} crossings", flush=True)
    assert found == set(selected.index), f"Missing {len(set(selected.index) - found)} cohort flights"
    report = {
        "method": "Viewer lattice_points on continuous native own-HMM climb edges; horizontal planes at every 10 m ASL; pool all crossings into 1 km Lambert-93 bins, retaining repeated contributions from each flight; all dates and heights pooled.",
        "interpretation": "Observed climb-crossing density. Repeated crossings are correlated and do not count independent atmospheric thermals. Vertical extent, launch exposure, routes and weather affect the density.",
        "cell_m": CELL_M,
        "plane_step_m": 10,
        "plane_reference": "Absolute adopted GNSS altitude (ASL), with planes at integer multiples of 10 m; regional analogue of the viewer cell-local AGL lattice.",
        "crossing_convention": "Upward and downward crossings within climb runs; half-open edges and terminal vertices, as in the viewer; horizontal coplanar edges omitted.",
        "source_flights": str(SOURCE / "flights.parquet"),
        "source_phase_segments": str(PHASE_SEGMENTS),
        "source_native_fixes": str(FIXES),
        "geometry_code": "src/soaring/viewer/thermal_daily.py:lattice_points; src/soaring/viewer/thermal_geometry.py:continuous_edges",
        "regions": {},
    }
    for i, name in enumerate(REGIONS):
        frame = selected.loc[selected.region_index.eq(i)]
        keys = list(cells[i])
        table = pd.DataFrame({
            "ix": [key[0] for key in keys], "iy": [key[1] for key in keys],
            "crossings": [cells[i][key] for key in keys],
        }).sort_values(["iy", "ix"], kind="stable").reset_index(drop=True)
        stem = name.lower().replace(" ", "-").replace("-lorraine", "")
        table.to_csv(OUT / f"{stem}-cells.csv", index=False)
        count = frame.task.value_counts().to_dict()
        report["regions"][name] = {
            "cohort_flights": len(frame), "task_counts": count,
            "open_fraction": count.get("open", 0) / len(frame),
            "crossing_flights": int(contributors[i]),
            "native_climb_edges": int(native_edges[i]),
            "crossings": int(totals[i]),
            "occupied_cells": len(table),
            "max_cell_crossings": int(table.crossings.max()),
            "csv": f"{stem}-cells.csv",
            "csv_sha256": hashlib.sha256((OUT / f"{stem}-cells.csv").read_bytes()).hexdigest(),
        }
        assert int(table.crossings.sum()) == int(totals[i])
    conditional = json.loads((ROOT / "thesis/generated/ch3_conditional.json").read_text())
    for name in REGIONS:
        key = name.lower().replace(" ", "_").replace("-", "_")
        expected = conditional["groups"][key]
        actual = report["regions"][name]
        assert actual["cohort_flights"] == expected["flights"]
        assert actual["task_counts"] == expected["circuit_counts"]
    (OUT / "counts-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["regions"], indent=2), flush=True)


if __name__ == "__main__":
    main()
