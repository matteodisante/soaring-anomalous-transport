"""Export crossings at successive heights for the four cells on the plane slide.

The saved plane-cells report fixes the cell bounds, terrain reference, time span,
and own-HMM segmentation. This script reads the same viewer climb edges and
applies the same half-open plane-intersection rule at each absolute altitude.
It requires the connected SSD; render_plane_cell_animation.py needs only these
exported arrays.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sqlite3
from pathlib import Path

import numpy as np

from soaring.viewer.thermal_explorer import load_explorer
from soaring.viewer.thermal_cache import segmentation_signature

HERE = Path(__file__).resolve().parent
OUT = HERE / "assets/plane-cells"
HEIGHTS_M = tuple(range(200, 1401, 200))


def crossings(edges, heights, bounds, start, end):
    """The viewer's half-open edge rule, evaluated for all heights at once."""
    if not len(edges):
        return [np.empty((0, 2)) for _ in heights]
    z0, z1 = edges[:, 2], edges[:, 6]
    delta = z1 - z0
    fraction = np.divide(
        np.asarray(heights)[:, None] - z0[None, :], delta[None, :],
        out=np.full((len(heights), len(edges)), np.nan),
        where=delta[None, :] != 0,
    )
    next_connected = np.zeros(len(edges), dtype=bool)
    next_connected[:-1] = (
        (edges[:-1, 7] == edges[1:, 3]) & (z1[:-1] == z0[1:])
    )
    use = ((fraction >= 0) & (fraction < 1)) | (
        (fraction == 1) & ~next_connected[None, :]
    )
    west, south, east, north = bounds
    frames = []
    for line, mask in zip(fraction, use, strict=True):
        f = line[mask]
        x = edges[mask, 0] + f * (edges[mask, 4] - edges[mask, 0])
        y = edges[mask, 1] + f * (edges[mask, 5] - edges[mask, 1])
        utc = edges[mask, 3] + f * (edges[mask, 7] - edges[mask, 3])
        keep = (x >= west) & (x < east) & (y >= south) & (y < north)
        keep &= (utc >= start) & (utc <= end)
        frames.append(np.column_stack((x[keep], y[keep])))
    return frames


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=OUT / "plane-cells-report.json")
    args = parser.parse_args()
    source = args.report
    report = json.loads(source.read_text())
    explorer = load_explorer()
    if explorer is None:
        raise SystemExit("Connect the SSD with the viewer's thermal-planes snapshot.")
    start, end = report["time_extent_utc_s"]
    saved_height = report["height_m"]
    saved_cells = {(cell.ix, cell.iy) for cell in explorer.store.cells()}
    index = explorer._index()
    cache_key = segmentation_signature(index, "own")
    snapshot = sqlite3.connect(f"file:{explorer.store.path}?mode=ro", uri=True)
    cache_path = index.path.with_name("thermal-climbs.sqlite3")
    cache = sqlite3.connect(f"file:{cache_path}?mode=ro", uri=True)
    manifest = {
        "source_report_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "method": "Viewer own-HMM continuous climb edges and the viewer's half-open plane-intersection rule at each absolute height; all dates and both disciplines.",
        "height_above_mean_terrain_m": list(HEIGHTS_M),
        "regions": {},
    }
    for slug, region in report["regions"].items():
        west, south, east, north = region["bounds_epsg2154"]
        assert (east - west) == (north - south)
        assert (east - west) % 5000 == 0
        ground = region["plane_altitude_m"] - saved_height
        frames = {height: [] for height in HEIGHTS_M}
        absolute_heights = [ground + height for height in HEIGHTS_M]
        for iy in range(south // 5000, north // 5000):
            for ix in range(west // 5000, east // 5000):
                print(f"{slug}: reading cell {ix}/{iy}", flush=True)
                if (ix, iy) in saved_cells:
                    rows = snapshot.execute(
                        """SELECT c.edges FROM visitors v JOIN climbs c
                        ON c.discipline=v.discipline AND c.flight_id=v.flight_id
                        AND c.ix=v.ix AND c.iy=v.iy AND c.source='own'
                        WHERE v.ix=? AND v.iy=? AND v.end>=? AND v.start<=?""",
                        (ix, iy, start, end),
                    )
                else:
                    rows = cache.execute(
                        "SELECT edges FROM climbs WHERE cache_key=? AND ix=? AND iy=?",
                        (cache_key, ix, iy),
                    )
                for (blob,) in rows:
                    if blob is None:
                        continue
                    with np.load(io.BytesIO(blob), allow_pickle=False) as saved:
                        edges = saved["edges"]
                    if not len(edges):
                        continue
                    edges = edges[(edges[:, 7] >= start) & (edges[:, 3] <= end)]
                    for height, xy in zip(
                        HEIGHTS_M,
                        crossings(edges, absolute_heights,
                                  (ix * 5000, iy * 5000, (ix + 1) * 5000, (iy + 1) * 5000),
                                  start, end),
                        strict=True,
                    ):
                        if len(xy):
                            frames[height].append(xy)
        arrays = {}
        counts = {}
        for height in HEIGHTS_M:
            xy = np.concatenate(frames[height]) if frames[height] else np.empty((0, 2))
            assert np.all((xy[:, 0] >= west) & (xy[:, 0] < east))
            assert np.all((xy[:, 1] >= south) & (xy[:, 1] < north))
            arrays[f"h{height}"] = xy
            counts[str(height)] = len(xy)
        if "crossings" in region:
            assert counts[str(saved_height)] == region["crossings"], (
                slug, counts[str(saved_height)], region["crossings"]
            )
        np.savez_compressed(OUT / f"{slug}-height-series.npz", **arrays)
        manifest["regions"][slug] = {
            "bounds_epsg2154": region["bounds_epsg2154"],
            "mean_terrain_m": ground,
            "counts": counts,
            "array_file": f"{slug}-height-series.npz",
        }
        print(f"{slug}: {counts}", flush=True)
    (OUT / "plane-cell-animation-report.json").write_text(json.dumps(manifest, indent=2) + "\n")
    snapshot.close()
    cache.close()


if __name__ == "__main__":
    main()
