"""Stream archived climb trajectories into bounded-memory residence-time products."""

from __future__ import annotations

import io
import json
import sqlite3
import time
from contextlib import suppress
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pyproj import Transformer

from ..analysis.preproc.enu import LocalFrame
from ..analysis.segmentation.config import load_segmentation_config
from ..reporting.disciplines import DISCIPLINES
from .geodesy import enu_to_geodetic
from .thermal_geometry import project
from .thermal_regions import REGIONS, extent
from .thermal_store import load_store
from .thermal_time import BASE_M, TimeGrid, cache_path, load_grids, save_grids


def region_grids():
    """Metric viewports enclosing the same five padded geographic regional boxes."""
    transform = Transformer.from_crs(4326, 2154, always_xy=True)
    result = {}
    for name, box in REGIONS.items():
        bounds = np.asarray(transform.transform_bounds(*extent(box), densify_pts=21))
        bounds[:2] = np.floor(bounds[:2] / BASE_M) * BASE_M
        bounds[2:] = np.ceil(bounds[2:] / BASE_M) * BASE_M
        result[f"region/{name}/own"] = TimeGrid(
            bounds,
            metadata={
                "name": name,
                "source": "own",
                "population": "all crossing trajectories",
            },
        )
    return result


def phase_edges(frame, origins, max_dt):
    """Consecutive climb decisions, never joined across flights, segments or gaps."""
    t = frame.t.to_numpy(float)
    dt = np.diff(t)
    use = (frame.phase.to_numpy()[:-1] == "climb") & (
        frame.phase.to_numpy()[1:] == "climb"
    )
    for column in ("flight_id", "segment_id"):
        values = frame[column].to_numpy()
        use &= values[:-1] == values[1:]
    use &= (dt > 0) & (dt <= max_dt)
    indices = np.flatnonzero(use)
    if not len(indices):
        return np.empty((0, 2)), np.empty((0, 2)), np.empty(0)
    positions = np.unique(np.r_[indices, indices + 1])
    selected = frame.iloc[positions]
    xy = np.empty((len(selected), 2))
    # Only climb endpoints need geodetic conversion; keep each flight's own origin.
    for fid, group_positions in selected.groupby(
        "flight_id", sort=False
    ).indices.items():
        group = selected.iloc[group_positions]
        if str(fid) not in origins:
            raise ValueError(f"Missing geographic origin for flight {fid}")
        lat, lon = enu_to_geodetic(
            group.E, group.N, group.z, LocalFrame(*origins[str(fid)])
        )
        x, y = project(lon, lat)
        xy[group_positions] = np.column_stack((x, y))
    return (
        xy[np.searchsorted(positions, indices)],
        xy[np.searchsorted(positions, indices + 1)],
        dt[indices],
    )


def prepare(
    *, regions=True, cells=True, limit_batches=None, output=None, progress=print
):
    """Read each HMM archive once and reuse both sources' saved cell edges.

    No decoder runs, no new plane intersections, no changes to the source archives.
    Limited builds require an explicit output and are marked incomplete.
    """
    if limit_batches is not None and output is None:
        raise ValueError("A benchmark must use a separate output path")
    start = time.perf_counter()
    target = cache_path() if output is None else output
    grids, report = (
        {},
        {
            "created": datetime.now(UTC).isoformat(),
            "base_m": BASE_M,
            "complete": limit_batches is None,
            "inputs": [],
            "stages": {},
        },
    )
    if not regions or not cells:
        with suppress(FileNotFoundError):
            existing = (
                target
                if target.exists()
                else target.with_name(".regional-" + target.name)
            )
            grids, previous_report = load_grids(existing)
            report["inputs"] = previous_report.get("inputs", [])
            report["stages"] = previous_report.get("stages", {})
    if regions:
        regional = region_grids()
        max_dt = 1.5 * load_segmentation_config().decision_step_s
        for disc in DISCIPLINES.values():
            root = disc.derived_dir()
            if root is None:
                continue
            path = root / "segmentation/phase_points.parquet"
            meta_path = root / "flights_meta.parquet"
            for p in (path, meta_path):
                stat = p.stat()
                report["inputs"].append(
                    {
                        "path": str(p),
                        "bytes": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                    }
                )
            meta = pd.read_parquet(
                meta_path, columns=["flight_id", "lat0", "lon0", "alt0"]
            )
            origins = {
                str(r.flight_id): (r.lat0, r.lon0, r.alt0)
                for r in meta.itertuples(index=False)
            }
            archive = pq.ParquetFile(path)
            columns = ["flight_id", "segment_id", "t", "E", "N", "z", "phase"]
            previous = None
            rows = edges = 0
            stage_start = time.perf_counter()
            for number, batch in enumerate(
                archive.iter_batches(batch_size=131072, columns=columns)
            ):
                if limit_batches is not None and number >= limit_batches:
                    break
                frame = batch.to_pandas()
                rows += len(frame)
                if previous is not None:
                    frame = pd.concat([previous, frame], ignore_index=True)
                previous = frame.iloc[-1:].copy()
                a, b, seconds = phase_edges(frame, origins, max_dt)
                edges += len(seconds)
                for grid in regional.values():
                    grid.add(a, b, seconds)
                if number % 25 == 0:
                    progress(
                        f"{disc.name}: {rows:,}/{archive.metadata.num_rows:,} "
                        "decisions; "
                        f"{edges:,} climb edges; "
                        f"{time.perf_counter() - stage_start:.1f} s"
                    )
            report["stages"][disc.name] = {
                "seconds": time.perf_counter() - stage_start,
                "rows": rows,
                "edges": edges,
                "total_rows": archive.metadata.num_rows,
            }
        grids.update(regional)
        # The private checkpoint is never opened automatically by the viewer.
        save_grids(grids, target.with_name(".regional-" + target.name), report)
        progress("Regional duration checkpoint saved")
    if cells:
        store = load_store()
        if store is None:
            raise FileNotFoundError("Prepare thermal-planes.sqlite3 first")
        cell_grids = {}
        for cell in store.cells():
            for source in ("own", "vilpellet"):
                key = f"cell/{cell.ix}/{cell.iy}/{source}"
                cell_grids[cell.ix, cell.iy, source] = TimeGrid(
                    cell.bounds,
                    metadata={
                        "source": source,
                        "cell": [cell.ix, cell.iy],
                        "terrain": cell.terrain,
                        "ground_m": cell.ground_m,
                        "visiting_flights": cell.flights,
                    },
                )
                grids[key] = cell_grids[cell.ix, cell.iy, source]
        stage_start = time.perf_counter()
        with sqlite3.connect(store.path.as_uri() + "?mode=ro", uri=True) as db:
            rows = db.execute("SELECT source,ix,iy,edges FROM climbs")
            products = 0
            for source, ix, iy, blob in rows:
                if limit_batches is not None and products >= limit_batches * 100:
                    break
                with np.load(io.BytesIO(blob), allow_pickle=False) as saved:
                    values = saved["edges"]
                grid = cell_grids[ix, iy, source]
                grid.add(values[:, :2], values[:, 4:6], values[:, 7] - values[:, 3])
                products += 1
                if products % 10000 == 0:
                    progress(
                        f"Cells: {products:,} saved flight/cell/source products; "
                        f"{time.perf_counter() - stage_start:.1f} s"
                    )
            metadata = dict(db.execute("SELECT key,value FROM metadata"))
            report["snapshot"] = {
                k: metadata.get(k)
                for k in ("archive_signature", "segmentation_signatures")
            }
        report["stages"]["cells"] = {
            "seconds": time.perf_counter() - stage_start,
            "products": products,
        }
    save_grids(grids, target, report)
    if cells and limit_batches is None:
        target.with_name(".regional-" + target.name).unlink(missing_ok=True)
    report["elapsed_s"] = time.perf_counter() - start
    report["output_bytes"] = target.stat().st_size
    report["grids"] = {
        key: {
            "hours": grid.hours,
            "occupied_pixels": len(grid.flat),
            "bounds": grid.bounds.tolist(),
        }
        for key, grid in grids.items()
    }
    target.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    progress(
        f"Wrote {target}: {report['output_bytes'] / 1e6:.2f} MB "
        f"in {report['elapsed_s']:.1f} s"
    )
    return report
