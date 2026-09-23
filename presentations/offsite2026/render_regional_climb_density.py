"""Regional climb-use maps for the offsite deck.

One paraglider contributes at most once to each 1 km cell.  The flight population is
exactly the fixed C10000 regional population used for the H comparison, with no date
filter.  A coloured cell records observed climb use, not a thermal source or an
independent sample of the atmosphere.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pyproj import Transformer

from soaring.analysis.preproc.enu import WGS84_A_M, WGS84_E2, geodetic_to_ecef
from soaring.analysis.regions import REGIONAL_BOXES
from soaring.viewer.geodesy import _ecef_to_geodetic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "assets/regional-climb"
SOURCE = Path("/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917/para")
PHASE_POINTS = Path(
    "/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/derived/segmentation/phase_points.parquet"
)
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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    selected = cohort()
    ids = pc.SetLookupOptions(value_set=pa.array(selected.index.to_numpy(dtype=str)))
    seen: set[tuple[int, str, int, int]] = set()
    points_by_region = np.zeros(len(REGIONS), dtype=np.int64)
    pf = pq.ParquetFile(PHASE_POINTS)
    for number, batch in enumerate(
        pf.iter_batches(batch_size=250_000, columns=["flight_id", "E", "N", "z", "phase"]), 1
    ):
        keep = pc.and_(pc.equal(batch.column("phase"), "climb"),
                       pc.is_in(batch.column("flight_id"), options=ids))
        if not pc.any(keep).as_py():
            continue
        tab = batch.filter(keep).to_pandas()
        tab = tab.join(selected[["lat0", "lon0", "alt0", "region_index"]], on="flight_id")
        tab = tab.loc[np.isfinite(tab[["E", "N", "z", "lat0", "lon0", "alt0"]]).all(axis=1)]
        if tab.empty:
            continue
        x, y = to_lambert(tab)
        ix = np.floor(np.asarray(x) / CELL_M).astype(np.int32)
        iy = np.floor(np.asarray(y) / CELL_M).astype(np.int32)
        points_by_region += np.bincount(tab.region_index.to_numpy(dtype=int), minlength=len(REGIONS))
        tuples = zip(tab.region_index.to_numpy(dtype=int), tab.flight_id.to_numpy(), ix, iy)
        seen.update(tuples)
        if number % 100 == 0:
            print(f"{number} batches, {len(seen):,} unique flight-cells", flush=True)
    cells: dict[int, dict[tuple[int, int], int]] = defaultdict(lambda: defaultdict(int))
    for region, _flight, ix, iy in seen:
        cells[int(region)][(int(ix), int(iy))] += 1
    report = {
        "method": "Unique C10000 paraglider flight with at least one own-HMM climb fix in a 1 km Lambert-93 cell; all dates and altitudes pooled; no calendar filter.",
        "interpretation": "Observed climb use, not direct thermal-source density; sampling, route choice and launch distribution remain confounders.",
        "cell_m": CELL_M,
        "source_flights": str(SOURCE / "flights.parquet"),
        "source_phase_points": str(PHASE_POINTS),
        "regions": {},
    }
    for i, name in enumerate(REGIONS):
        frame = selected.loc[selected.region_index.eq(i)]
        keys = list(cells[i])
        table = pd.DataFrame({
            "ix": [key[0] for key in keys], "iy": [key[1] for key in keys],
            "flights": [cells[i][key] for key in keys],
        }).sort_values(["iy", "ix"], kind="stable").reset_index(drop=True)
        stem = name.lower().replace(" ", "-").replace("-lorraine", "")
        table.to_csv(OUT / f"{stem}-cells.csv", index=False)
        count = frame.task.value_counts().to_dict()
        report["regions"][name] = {
            "cohort_flights": len(frame), "task_counts": count,
            "open_fraction": count.get("open", 0) / len(frame),
            "climb_fixes": int(points_by_region[i]),
            "occupied_cells": len(table),
            "flight_cell_visits": int(table.flights.sum()),
            "max_cell_flights": int(table.flights.max()),
            "csv": f"{stem}-cells.csv",
            "csv_sha256": hashlib.sha256((OUT / f"{stem}-cells.csv").read_bytes()).hexdigest(),
        }
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
