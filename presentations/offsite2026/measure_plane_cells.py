"""Climb crossings of one horizontal plane in four regional 20 km cells.

Everything reuses the viewer's thermal-plane machinery (``thermal_explorer``): the
archive census of flights crossing each 5 km cell, its IGN terrain means, the
whole-flight own-HMM decoding with its persistent climb cache, and the absolute
plane intersection of the expanded neighbourhood view.

Selection: in each regional box, the 20 km Lambert-93 cell (edges at multiples of
20 km, i.e. 4 x 4 viewer cells) lying wholly inside the box and crossed by the most
distinct flights, over all dates and both disciplines.
Plane: at height H = 800 m above the cell's mean IGN RGE ALTI terrain, the average of
its sixteen 5 km viewer references (equal areas). One horizontal plane, not
terrain-following.

Needs the SSD, the viewer census and internet for missing IGN terrain. Missing climb
products are decoded once, in parallel, and stored in the viewer's
``thermal-climbs.sqlite3``.
"""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
from PIL import Image
from pyproj import Transformer

from soaring.analysis.regions import REGIONAL_BOXES
from soaring.reporting.disciplines import DISCIPLINES
from soaring.viewer.thermal_explorer import load_explorer
from soaring.viewer.thermal_geometry import plane_intersections
from soaring.viewer.thermal_ground import mean_terrain
from soaring.viewer.thermal_imagery import _download
from soaring.viewer.thermal_prepare import prepare_climbs
from soaring.viewer.thermal_ridges import DATASET_URL, LAYER, SERVICE

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "assets/plane-cells"
HEIGHT_M = 800
SOURCE = "own"
BLOCK = 4  # viewer cells per side of a 20 km cell
SIZE_KM = BLOCK * 5
DEM_PIXELS = 800  # 25 m sampling over 20 km, as the viewer's 5 km references
WORKERS = 6
REGIONS = {
    "alps": "Alps",
    "pyrenees": "Pyrenees",
    "channel-coast": "Channel Coast",
    "champagne": "Champagne-Lorraine",
}
TO_WGS84 = Transformer.from_crs(2154, 4326, always_xy=True)
TO_LAMBERT = Transformer.from_crs(4326, 2154, always_xy=True)
HOTSPOT_BIN_M = 250


def ranked_blocks(index) -> dict[str, pd.DataFrame]:
    """Rank the SIZE_KM cells inside each box by distinct crossing flights."""
    with sqlite3.connect(f"file:{index.path}?mode=ro", uri=True) as db:
        visits = pd.read_sql("SELECT discipline, flight_id, ix, iy FROM visits", db)
    visits["bx"], visits["by"] = visits.ix // BLOCK, visits.iy // BLOCK
    counts = (visits.drop_duplicates(["discipline", "flight_id", "bx", "by"])
              .groupby(["bx", "by"]).size().rename("flights").reset_index())
    size = BLOCK * 5000
    ranked = {}
    for slug, name in REGIONS.items():
        west, east, south, north = REGIONAL_BOXES[name]
        inside = np.ones(len(counts), dtype=bool)
        for dx in (0, size):
            for dy in (0, size):
                lon, lat = TO_WGS84.transform((counts.bx * size + dx).to_numpy(),
                                              (counts.by * size + dy).to_numpy())
                inside &= (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)
        ranked[slug] = (counts.loc[inside]
                        .sort_values(["flights", "bx", "by"], ascending=[False, True, True])
                        .reset_index(drop=True))
    return ranked


def fetch_dem(bounds, pixels=DEM_PIXELS):
    """One official IGN float elevation window over the whole cell."""
    url = SERVICE + "?" + urlencode({
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": LAYER,
        "STYLES": "normal", "CRS": "EPSG:2154", "BBOX": ",".join(map(str, bounds)),
        "WIDTH": pixels, "HEIGHT": pixels, "FORMAT": "image/tiff",
    })
    raw = _download(url)
    with Image.open(io.BytesIO(raw)) as im:
        if im.mode != "F" or im.size != (pixels, pixels):
            raise ValueError("IGN response must be a float elevation raster")
        z = np.asarray(im, dtype=float)
    return raw, z, url


def track_origins(index) -> pd.DataFrame:
    """Local-frame origin (first retained fix) of every processed flight, in Lambert-93."""
    frames = []
    for name in index.disciplines:
        path = DISCIPLINES[name].config().derived_dir / "flights_meta.parquet"
        meta = pd.read_parquet(path, columns=["flight_id", "lat0", "lon0"])
        meta["discipline"], meta["flight_id"] = name, meta.flight_id.astype(str)
        frames.append(meta.dropna())
    origins = pd.concat(frames, ignore_index=True)
    origins["x0"], origins["y0"] = TO_LAMBERT.transform(origins.lon0.to_numpy(), origins.lat0.to_numpy())
    return origins.drop_duplicates(["discipline", "flight_id"])


def hotspot(points, bounds, origins):
    """Densest 250 m bin, and how far the contributing flights started from it."""
    west, south, east, north = bounds
    bins = int((east - west) // HOTSPOT_BIN_M)
    counts, xe, ye = np.histogram2d(points.x, points.y, bins=bins, range=[[west, east], [south, north]])
    i, j = np.unravel_index(counts.argmax(), counts.shape)
    x, y = (xe[i] + xe[i + 1]) / 2, (ye[j] + ye[j + 1]) / 2
    flights = points[["discipline", "flight_id"]].drop_duplicates().astype({"flight_id": str})
    starts = flights.merge(origins, on=["discipline", "flight_id"], how="left", validate="1:1")
    distance = np.hypot(starts.x0 - x, starts.y0 - y)
    return {
        "centre_epsg2154": [x, y], "centre_lon_lat": TO_WGS84.transform(x, y),
        "crossings_in_bin": int(counts[i, j]),
        "flights_without_origin": int(starts.x0.isna().sum()),
        "flights_started_within_1km": float(np.mean(distance < 1000)),
        "flights_started_within_3km": float(np.mean(distance < 3000)),
        "flights_started_inside_cell": float(np.mean(
            starts.x0.between(west, east, inclusive="left") & starts.y0.between(south, north, inclusive="left"))),
    }


def main() -> None:
    explorer = load_explorer()
    if explorer is None:
        raise SystemExit("Connect the SSD with the viewer's thermal-planes snapshot.")
    index = explorer._index()
    start, end = explorer.time_extent()
    OUT.mkdir(parents=True, exist_ok=True)
    ranked = ranked_blocks(index)
    origins = track_origins(index)
    report = {
        "method": (
            "Viewer thermal-plane explorer: census visitors of each 5 km cell, whole-flight "
            "own-HMM climb edges (saved or decoded into the viewer climb cache), and "
            "plane_intersections at one absolute altitude, as in the expanded "
            "neighbourhood view. All dates, both disciplines."
        ),
        "selection": (
            f"Per regional box, the {SIZE_KM} km Lambert-93 cell (edges at multiples of "
            f"{SIZE_KM} km, {BLOCK} x {BLOCK} viewer cells) wholly inside the box with the "
            "most distinct crossing flights in the viewer census; ties by grid coordinates."
        ),
        "plane": (
            f"At height H = {HEIGHT_M} m above the mean IGN RGE ALTI terrain of the cell, "
            f"the average of its {BLOCK * BLOCK} 5 km viewer DEM means (equal areas). "
            "One horizontal plane."
        ),
        "size_km": SIZE_KM,
        "height_m": HEIGHT_M,
        "segmentation": SOURCE,
        "time_extent_utc_s": [start, end],
        "census": str(index.path),
        "dem_dataset": DATASET_URL,
        "regions": {},
        "code_sha256": {},
    }
    macros = [f"\\newcommand{{\\PlaneCellHeight}}{{{HEIGHT_M}}}",
              f"\\newcommand{{\\PlaneCellSize}}{{{SIZE_KM}}}"]
    blocks = {slug: ranked[slug].iloc[0] for slug in REGIONS}
    squares = {
        slug: [
            explorer.resolve_cell(BLOCK * int(best.bx) + dx, BLOCK * int(best.by) + dy,
                                  kind="none", progress=print)
            for dy in range(BLOCK) for dx in range(BLOCK)
        ]
        for slug, best in blocks.items()
    }
    # Decode every missing flight once, in parallel, for all explored squares it
    # crosses; read_plane below then only reads the cache. Ranked viewer cells keep
    # their saved planes.
    saved = {(cell.ix, cell.iy) for cell in explorer.store.cells()}
    explored = [c for cells in squares.values() for c in cells if (c.ix, c.iy) not in saved]
    prepare_climbs(index, workers=WORKERS, cells=explored, sources=(SOURCE,),
                   progress=lambda m: print(m, flush=True))
    for slug, name in REGIONS.items():
        best = blocks[slug]
        bx, by = int(best.bx), int(best.by)
        cells = squares[slug]
        references = [explorer.terrain_reference(cell) for cell in cells]
        for cell, reference in zip(cells, references, strict=True):
            assert np.isclose(cell.ground_m, reference["mean_m"])
        ground = float(np.mean([cell.ground_m for cell in cells]))
        altitude = ground + HEIGHT_M
        frames, coverage = [], []
        for cell in cells:
            print(f"{name}: cell {cell.ix}/{cell.iy}, {cell.flights:,} visitors", flush=True)
            plane = explorer.read_plane(cell, start, end, SOURCE, progress=print, use_edges=True)
            points = plane_intersections(plane.edges, cell, HEIGHT_M, start, end,
                                         altitude_m=altitude)
            frames.append(points)
            coverage.append({
                "ix": cell.ix, "iy": cell.iy, "terrain_label": cell.terrain,
                "visitors": cell.flights, "mean_terrain_m": cell.ground_m,
                "selected": plane.selected, "decoded": plane.decoded,
                "unclassified": plane.unclassified, "unavailable": plane.unavailable,
                "unknown_clock": plane.unknown_clock, "cached": plane.cached,
                "crossings": len(points),
            })
        points = pd.concat(frames, ignore_index=True)[["x", "y", "utc", "discipline", "flight_id"]]
        size = BLOCK * 5000
        bounds = (bx * size, by * size, (bx + 1) * size, (by + 1) * size)
        assert points.x.between(bounds[0], bounds[2], inclusive="left").all()
        assert points.y.between(bounds[1], bounds[3], inclusive="left").all()
        raw, dem, url = fetch_dem(bounds)
        dem_mean = mean_terrain(dem, bounds, bounds)["mean_m"]
        (OUT / f"{slug}-dem.tif").write_bytes(raw)
        csv = points.to_csv(index=False)
        (OUT / f"{slug}-points.csv").write_text(csv)
        flights = len(points[["discipline", "flight_id"]].drop_duplicates())
        centre = TO_WGS84.transform((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
        report["regions"][slug] = {
            "region": name,
            "block": [bx, by],
            "bounds_epsg2154": bounds,
            "centre_lon_lat": centre,
            "census_flights": int(best.flights),
            "runner_up_flights": [int(n) for n in ranked[slug].flights.iloc[1:3]],
            "mean_terrain_m": ground,
            "plane_altitude_m": altitude,
            "dem": {
                "file": f"{slug}-dem.tif", "source_url": url,
                "response_sha256": hashlib.sha256(raw).hexdigest(),
                "mean_m": dem_mean, "mean_minus_cell_average_m": dem_mean - ground,
                "min_m": float(dem.min()), "max_m": float(dem.max()),
                "area_above_plane": float(np.mean(dem > altitude)),
            },
            "cells": coverage,
            "crossings": len(points),
            "flights": flights,
            "discipline_crossings": points.discipline.value_counts().to_dict(),
            "points_sha256": hashlib.sha256(csv.encode()).hexdigest(),
            "hotspot": hotspot(points, bounds, origins),
        }
        tag = "".join(part.capitalize() for part in slug.split("-"))
        macros += [
            f"\\newcommand{{\\PlaneCell{tag}Crossings}}{{{len(points):,}}}",
            f"\\newcommand{{\\PlaneCell{tag}Flights}}{{{flights:,}}}",
            f"\\newcommand{{\\PlaneCell{tag}Ground}}{{{ground:,.0f}}}",
            f"\\newcommand{{\\PlaneCell{tag}Altitude}}{{{altitude:,.0f}}}",
            f"\\newcommand{{\\PlaneCell{tag}AboveShare}}{{{100 * np.mean(dem > altitude):.0f}}}",
        ]
        spot = report["regions"][slug]["hotspot"]
        macros += [
            f"\\newcommand{{\\PlaneCell{tag}StartOne}}{{{100 * spot['flights_started_within_1km']:.0f}}}",
            f"\\newcommand{{\\PlaneCell{tag}StartThree}}{{{100 * spot['flights_started_within_3km']:.0f}}}",
        ]
        print(f"{name}: H = {altitude:.0f} m, {len(points):,} crossings from {flights:,} flights; "
              f"DEM mean check {dem_mean - ground:+.2f} m", flush=True)
    for rel in (
        "presentations/offsite2026/measure_plane_cells.py",
        "src/soaring/viewer/thermal_explorer.py", "src/soaring/viewer/thermal_geometry.py",
        "src/soaring/viewer/thermal_ground.py", "src/soaring/viewer/thermal_prepare.py",
        "src/soaring/viewer/thermal_store.py", "src/soaring/viewer/thermal_cache.py",
    ):
        report["code_sha256"][rel] = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    (OUT / "plane-cells-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "plane-cells-values.tex").write_text("\n".join(macros) + "\n")


if __name__ == "__main__":
    main()
